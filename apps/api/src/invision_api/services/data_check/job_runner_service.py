from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

import logging

from invision_api.models.enums import (
    ApplicationStage,
    DataCheckRunStatus,
    DataCheckUnitStatus,
    DataCheckUnitType,
    JobStatus,
)
from invision_api.repositories import admissions_repository, commission_repository, data_check_repository
from invision_api.services.data_check import orchestrator_service
from invision_api.services.data_check.job_registry import REGISTRY
from invision_api.services.data_check.status_service import TERMINAL_UNIT_STATUSES, compute_run_status
from invision_api.services.stage_transition_policy import TransitionContext, TransitionName, apply_transition

logger = logging.getLogger(__name__)


def _to_stage_status(run_status: str) -> str:
    if run_status in {DataCheckRunStatus.pending.value, DataCheckRunStatus.running.value}:
        return "in_review"
    if run_status == DataCheckRunStatus.ready.value:
        return "approved"
    if run_status in {DataCheckRunStatus.partial.value, DataCheckRunStatus.failed.value}:
        return "needs_attention"
    return "in_review"


def _update_analysis_job(
    db: Session,
    *,
    analysis_job_id: UUID | None,
    status: str,
    last_error: str | None = None,
) -> None:
    if not analysis_job_id:
        return
    job = admissions_repository.get_analysis_job(db, analysis_job_id)
    if not job:
        return
    admissions_repository.update_analysis_job(
        db,
        job,
        status=status,
        attempts=(job.attempts or 0) + 1 if status in {JobStatus.running.value, JobStatus.failed.value} else job.attempts,
        last_error=last_error,
    )


_ADVANCE_STATUSES = {DataCheckRunStatus.ready.value, DataCheckRunStatus.partial.value}


def _try_auto_advance(
    db: Session,
    *,
    run_computed: object,
    app: object | None,
    application_id: UUID,
) -> None:
    """Auto-advance from initial_screening to application_review.

    Fires when the data-check run reaches ``ready`` (all units green) or ``partial``
    (only optional units failed/need-review).  ``failed`` (required units broken) stays
    on initial_screening for manual commission intervention.
    """
    if not app or getattr(app, "current_stage", None) != ApplicationStage.initial_screening.value:
        return
    if getattr(run_computed, "status", None) not in _ADVANCE_STATUSES:
        return

    note = (
        "Auto-advanced: all data-check units completed."
        if run_computed.status == DataCheckRunStatus.ready.value
        else "Auto-advanced: required units completed; optional units need attention."
    )
    try:
        apply_transition(
            db,
            app,
            TransitionContext(
                application_id=app.id,
                transition=TransitionName.screening_passed,
                actor_user_id=None,
                actor_type="system",
                internal_note=note,
            ),
        )
        commission_repository.upsert_projection_for_application(db, app)
        logger.info("auto_advance application=%s initial_screening -> application_review status=%s", application_id, run_computed.status)
    except Exception:
        logger.exception("auto_advance_failed application=%s", application_id)


def run_unit(
    db: Session,
    *,
    application_id: UUID,
    run_id: UUID,
    unit_type: DataCheckUnitType,
    analysis_job_id: UUID | None = None,
) -> None:
    run = data_check_repository.get_run(db, run_id)
    if not run:
        _update_analysis_job(db, analysis_job_id=analysis_job_id, status=JobStatus.failed.value, last_error="run_not_found")
        return
    check = data_check_repository.get_check(db, run_id, unit_type.value)
    if not check:
        _update_analysis_job(
            db,
            analysis_job_id=analysis_job_id,
            status=JobStatus.failed.value,
            last_error=f"check_not_found:{unit_type.value}",
        )
        return

    _update_analysis_job(db, analysis_job_id=analysis_job_id, status=JobStatus.running.value)

    now = datetime.now(tz=UTC)
    data_check_repository.update_check_status(
        db,
        check=check,
        status=DataCheckUnitStatus.running.value,
        attempts=(check.attempts or 0) + 1,
    )
    data_check_repository.upsert_unit_result(
        db,
        run_id=run_id,
        application_id=application_id,
        unit_type=unit_type.value,
        status=DataCheckUnitStatus.running.value,
        result_payload=check.result_payload,
        warnings=[],
        errors=[],
        explainability=[],
        manual_review_required=False,
        attempts=check.attempts,
        started_at=now,
        finished_at=None,
    )
    if run.overall_status == DataCheckRunStatus.pending.value:
        data_check_repository.update_run_status(
            db,
            run=run,
            status=DataCheckRunStatus.running.value,
            explainability=["Data-check pipeline started processing units."],
        )
    commission_repository.set_stage_status(
        db,
        application_id=application_id,
        stage=ApplicationStage.initial_screening.value,
        status="in_review",
        actor_user_id=None,
        reason_comment=f"Data-check unit started: {unit_type.value}",
    )
    db.flush()

    processor = REGISTRY[unit_type]
    try:
        result = processor(db, application_id, run.candidate_id, run_id)
        final_status = result.status
        if final_status not in {
            DataCheckUnitStatus.completed.value,
            DataCheckUnitStatus.failed.value,
            DataCheckUnitStatus.manual_review_required.value,
        }:
            final_status = DataCheckUnitStatus.failed.value
            result.errors.append(f"Unsupported unit status: {result.status}")
        data_check_repository.update_check_status(
            db,
            check=check,
            status=final_status,
            result_payload=result.payload,
            last_error="; ".join(result.errors) if result.errors else None,
        )
        data_check_repository.upsert_unit_result(
            db,
            run_id=run_id,
            application_id=application_id,
            unit_type=unit_type.value,
            status=final_status,
            result_payload=result.payload,
            warnings=result.warnings,
            errors=result.errors,
            explainability=result.explainability,
            manual_review_required=result.manual_review_required,
            attempts=check.attempts,
            started_at=check.started_at,
            finished_at=check.finished_at,
        )
    except Exception as exc:  # noqa: BLE001
        err_text = str(exc)
        data_check_repository.update_check_status(
            db,
            check=check,
            status=DataCheckUnitStatus.failed.value,
            last_error=err_text,
        )
        data_check_repository.upsert_unit_result(
            db,
            run_id=run_id,
            application_id=application_id,
            unit_type=unit_type.value,
            status=DataCheckUnitStatus.failed.value,
            result_payload=None,
            warnings=[],
            errors=[err_text],
            explainability=["Unit execution raised an exception."],
            manual_review_required=True,
            attempts=check.attempts,
            started_at=check.started_at,
            finished_at=check.finished_at,
        )

    checks = data_check_repository.list_checks_for_run(db, run_id)
    status_map = {}
    for c in checks:
        try:
            status_map[DataCheckUnitType(c.check_type)] = c.status
        except ValueError:
            continue
    run_computed = compute_run_status(status_map)
    data_check_repository.update_run_status(
        db,
        run=run,
        status=run_computed.status,
        warnings=run_computed.warnings,
        errors=run_computed.errors,
        explainability=run_computed.explainability,
    )

    stage_status = _to_stage_status(run_computed.status)
    commission_repository.set_stage_status(
        db,
        application_id=application_id,
        stage=ApplicationStage.initial_screening.value,
        status=stage_status,
        actor_user_id=None,
        reason_comment=f"Data-check status updated: {run_computed.status}",
    )
    commission_repository.set_attention_flag(
        db,
        application_id=application_id,
        stage=ApplicationStage.initial_screening.value,
        value=run_computed.manual_review_required,
    )

    app = data_check_repository.get_application(db, application_id)
    if app:
        commission_repository.upsert_projection_for_application(db, app)

    _try_auto_advance(db, run_computed=run_computed, app=app, application_id=application_id)

    try:
        orchestrator_service.enqueue_ready_followup_jobs(db, application_id=application_id, run_id=run_id)
    except Exception:
        logger.exception("followup_enqueue_failed application=%s run=%s", application_id, run_id)

    final_check = data_check_repository.get_check(db, run_id, unit_type.value)
    if final_check and final_check.status == DataCheckUnitStatus.failed.value:
        _update_analysis_job(
            db,
            analysis_job_id=analysis_job_id,
            status=JobStatus.failed.value,
            last_error=final_check.last_error,
        )
    else:
        _update_analysis_job(db, analysis_job_id=analysis_job_id, status=JobStatus.completed.value)
