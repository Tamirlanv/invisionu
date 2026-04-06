from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.candidate_validation_orchestration import CandidateValidationRun
from invision_api.models.enums import DataCheckRunStatus, DataCheckUnitStatus, DataCheckUnitType
from invision_api.repositories import commission_repository, data_check_repository
from invision_api.services import job_dispatcher_service
from invision_api.services.data_check.job_registry import FIRST_WAVE_UNITS
from invision_api.services.data_check.status_service import TERMINAL_UNIT_STATUSES, UNIT_POLICIES, dependencies_met

logger = logging.getLogger(__name__)

SWEEP_STALE_MINUTES = 10
# Wall-clock max time a run may stay in pending/running before forced terminalization (orange card).
RUN_PROCESSING_SLA_MINUTES_DEFAULT = 30
_SLA_TIMEOUT_MSG = "Превышено время ожидания обработки данных (SLA)."


def _run_processing_sla_minutes() -> int:
    raw = os.environ.get("DATA_CHECK_RUN_SLA_MINUTES", str(RUN_PROCESSING_SLA_MINUTES_DEFAULT))
    try:
        return max(1, int(raw))
    except ValueError:
        return RUN_PROCESSING_SLA_MINUTES_DEFAULT


def _terminalize_run_on_sla_timeout(db: Session, run: CandidateValidationRun) -> bool:
    """Mark all non-terminal units failed with SLA message; recompute run and projection."""
    from invision_api.services.data_check.job_runner_service import _try_auto_advance
    from invision_api.services.data_check.status_service import TERMINAL_UNIT_STATUSES, compute_run_status

    now = datetime.now(tz=UTC)
    touched = False
    for unit in UNIT_POLICIES:
        check = data_check_repository.get_check(db, run.id, unit.value)
        if not check:
            continue
        if check.status in TERMINAL_UNIT_STATUSES:
            continue
        data_check_repository.update_check_status(
            db,
            check=check,
            status=DataCheckUnitStatus.failed.value,
            last_error=_SLA_TIMEOUT_MSG,
        )
        data_check_repository.upsert_unit_result(
            db,
            run_id=run.id,
            application_id=run.application_id,
            unit_type=unit.value,
            status=DataCheckUnitStatus.failed.value,
            result_payload=None,
            warnings=[],
            errors=[_SLA_TIMEOUT_MSG],
            explainability=["Data-check SLA wall-clock limit exceeded; unit marked failed."],
            manual_review_required=True,
            attempts=check.attempts or 0,
            started_at=check.started_at,
            finished_at=now,
        )
        touched = True

    if not touched:
        return False

    checks_all = data_check_repository.list_checks_for_run(db, run.id)
    status_map: dict[DataCheckUnitType, str] = {}
    for c in checks_all:
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
    try:
        app_row = data_check_repository.get_application(db, run.application_id)
        if app_row:
            commission_repository.upsert_projection_for_application(db, app_row)
    except Exception:
        logger.exception("sla_terminalize_projection_failed run=%s", run.id)

    if run_computed.status in {
        DataCheckRunStatus.ready.value,
        DataCheckRunStatus.partial.value,
        DataCheckRunStatus.failed.value,
    }:
        app = data_check_repository.get_application(db, run.application_id)
        _try_auto_advance(db, run_computed=run_computed, app=app, application_id=run.application_id)

    logger.warning("sla_terminalize run=%s new_status=%s", run.id, run_computed.status)
    return True


def _retire_noncanonical_run(db: Session, *, run: CandidateValidationRun) -> bool:
    """Mark non-canonical active run terminal so sweep does not process it forever."""
    reason_code = "noncanonical_run_retired"
    now = datetime.now(tz=UTC)
    touched = False

    checks = data_check_repository.list_checks_for_run(db, run.id)
    for check in checks:
        if check.status in TERMINAL_UNIT_STATUSES:
            continue
        data_check_repository.update_check_status(
            db,
            check=check,
            status=DataCheckUnitStatus.failed.value,
            last_error=reason_code,
        )
        touched = True
        try:
            unit_type = DataCheckUnitType(check.check_type)
        except ValueError:
            continue
        data_check_repository.upsert_unit_result(
            db,
            run_id=run.id,
            application_id=run.application_id,
            unit_type=unit_type.value,
            status=DataCheckUnitStatus.failed.value,
            result_payload=check.result_payload,
            warnings=[],
            errors=[reason_code],
            explainability=["Run retired because it is non-canonical for the active data-check policy."],
            manual_review_required=True,
            attempts=check.attempts or 0,
            started_at=check.started_at,
            finished_at=check.finished_at or now,
        )

    if run.overall_status in {
        DataCheckRunStatus.pending.value,
        DataCheckRunStatus.running.value,
        "processing",
    }:
        data_check_repository.update_run_status(
            db,
            run=run,
            status=DataCheckRunStatus.failed.value,
            warnings=[],
            errors=[reason_code],
            explainability=["Run retired because it is non-canonical for the active data-check policy."],
        )
        touched = True

    if touched:
        try:
            app_row = data_check_repository.get_application(db, run.application_id)
            if app_row:
                commission_repository.upsert_projection_for_application(db, app_row)
        except Exception:
            logger.exception("sweep_noncanonical_projection_failed run=%s", run.id)
    return touched


def enqueue_first_wave_jobs(
    db: Session,
    *,
    application_id: UUID,
    run_id: UUID,
    queue_report: job_dispatcher_service.QueueDispatchReport | None = None,
    strict: bool = False,
) -> job_dispatcher_service.QueueDispatchReport:
    report = queue_report or job_dispatcher_service.QueueDispatchReport()
    for unit_type in FIRST_WAVE_UNITS:
        check = data_check_repository.get_check(db, run_id, unit_type.value)
        if not check:
            continue
        if check.status not in {DataCheckUnitStatus.pending.value, DataCheckUnitStatus.queued.value}:
            continue
        data_check_repository.update_check_status(db, check=check, status=DataCheckUnitStatus.queued.value)
        job_dispatcher_service.enqueue_data_check_unit_job(
            db,
            application_id=application_id,
            run_id=run_id,
            unit_type=unit_type,
            queue_report=report,
            strict=strict,
        )
    return report


def enqueue_ready_followup_jobs(
    db: Session,
    *,
    application_id: UUID,
    run_id: UUID,
    queue_report: job_dispatcher_service.QueueDispatchReport | None = None,
    strict: bool = False,
) -> list[str]:
    report = queue_report
    checks = data_check_repository.list_checks_for_run(db, run_id)
    status_map = {}
    by_unit: dict[DataCheckUnitType, object] = {}
    for check in checks:
        try:
            unit = DataCheckUnitType(check.check_type)
        except ValueError:
            continue
        status_map[unit] = check.status
        by_unit[unit] = check

    enqueued: list[str] = []
    for unit, policy in UNIT_POLICIES.items():
        if not policy.dependencies:
            continue
        check = by_unit.get(unit)
        if not check:
            continue
        if check.status not in {DataCheckUnitStatus.pending.value, DataCheckUnitStatus.queued.value}:
            continue
        if not dependencies_met(unit=unit, statuses=status_map):
            continue
        data_check_repository.update_check_status(db, check=check, status=DataCheckUnitStatus.queued.value)
        job_dispatcher_service.enqueue_data_check_unit_job(
            db,
            application_id=application_id,
            run_id=run_id,
            unit_type=unit,
            queue_report=report,
            strict=strict,
        )
        enqueued.append(unit.value)
    return enqueued


def sweep_stuck_runs(db: Session) -> int:
    """Detect and recover runs that have been stuck (pending/running) for too long.

    For each stuck run:
    0. Runs past wall-clock SLA (``created_at``) are terminalized (failed/partial) so cards do not
       stay blue indefinitely while ``updated_at`` keeps moving.
    1. Checks older than the stale threshold in queued/running are either re-enqueued
       (if under max attempts) or marked failed.
    2. First-wave jobs are enqueued again (covers units that stayed ``pending`` if enqueue failed
       at submit; avoids re-enqueueing dependency-wave units too early).
    3. Follow-up jobs whose dependencies are now terminal but were never enqueued get
       re-enqueued.
    4. Run status is recomputed after recovery actions; commission projection is refreshed.

    Returns the number of runs that were touched.
    """
    from invision_api.services.data_check.contracts import DataCheckUnitPolicy
    from invision_api.services.data_check.status_service import compute_run_status

    threshold = datetime.now(tz=UTC) - timedelta(minutes=SWEEP_STALE_MINUTES)
    sla_mins = _run_processing_sla_minutes()
    sla_deadline = datetime.now(tz=UTC) - timedelta(minutes=sla_mins)

    stuck_runs = data_check_repository.list_stuck_runs(db, stale_threshold=threshold)
    sla_runs = data_check_repository.list_runs_past_processing_sla(db, sla_deadline=sla_deadline)

    run_by_id: dict[UUID, CandidateValidationRun] = {}
    for r in stuck_runs:
        run_by_id[r.id] = r
    for r in sla_runs:
        run_by_id[r.id] = r

    if not run_by_id:
        return 0

    sla_ids = {r.id for r in sla_runs}
    recovered = 0
    skipped_noncanonical = 0
    retired_noncanonical = 0
    for run_id in sorted(run_by_id.keys(), key=lambda x: str(x)):
        run = data_check_repository.get_run(db, run_id)
        if not run:
            continue
        if run.overall_status not in {
            DataCheckRunStatus.pending.value,
            DataCheckRunStatus.running.value,
            "processing",  # legacy; normalized by migration, kept for safety
        }:
            continue

        repaired_missing = data_check_repository.repair_missing_policy_checks_for_run(
            db,
            run_id=run.id,
            application_id=run.application_id,
        )
        if repaired_missing > 0:
            logger.warning("sweep_repair_missing_checks run=%s created=%d", run.id, repaired_missing)

        if not data_check_repository.run_has_canonical_policy_checks(db, run.id):
            skipped_noncanonical += 1
            if _retire_noncanonical_run(db, run=run):
                retired_noncanonical += 1
                recovered += 1
            db.flush()
            continue

        if run_id in sla_ids:
            touched = repaired_missing > 0
            if _terminalize_run_on_sla_timeout(db, run):
                touched = True
            if touched:
                recovered += 1
            db.flush()
            continue

        stuck_checks = data_check_repository.list_stuck_checks(db, run_id=run.id, stale_threshold=threshold)
        touched = repaired_missing > 0

        for check in stuck_checks:
            try:
                unit_type = DataCheckUnitType(check.check_type)
            except ValueError:
                continue

            policy: DataCheckUnitPolicy = UNIT_POLICIES.get(unit_type)
            max_attempts = policy.max_attempts if policy else 3
            current_attempts = check.attempts or 0

            if current_attempts >= max_attempts:
                data_check_repository.update_check_status(
                    db,
                    check=check,
                    status=DataCheckUnitStatus.failed.value,
                    last_error=f"exceeded_max_attempts ({max_attempts})",
                )
                logger.warning(
                    "sweep_mark_failed run=%s unit=%s attempts=%d",
                    run.id, check.check_type, current_attempts,
                )
                touched = True
            else:
                data_check_repository.update_check_status(
                    db, check=check, status=DataCheckUnitStatus.queued.value
                )
                try:
                    job_dispatcher_service.enqueue_data_check_unit_job(
                        db,
                        application_id=run.application_id,
                        run_id=run.id,
                        unit_type=unit_type,
                    )
                    logger.info(
                        "sweep_reenqueue run=%s unit=%s attempt=%d",
                        run.id, check.check_type, current_attempts + 1,
                    )
                except Exception:
                    logger.exception("sweep_reenqueue_failed run=%s unit=%s", run.id, check.check_type)
                touched = True

        fw_report = job_dispatcher_service.QueueDispatchReport()
        try:
            enqueue_first_wave_jobs(
                db,
                application_id=run.application_id,
                run_id=run.id,
                queue_report=fw_report,
            )
        except Exception:
            logger.exception("sweep_first_wave_failed run=%s", run.id)
        else:
            if fw_report.enqueued > 0:
                touched = True

        try:
            followup_enqueued = enqueue_ready_followup_jobs(db, application_id=run.application_id, run_id=run.id)
        except Exception:
            logger.exception("sweep_followup_failed run=%s", run.id)
        else:
            if followup_enqueued:
                touched = True

        checks_all = data_check_repository.list_checks_for_run(db, run.id)
        status_map = {}
        for c in checks_all:
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

        try:
            app_row = data_check_repository.get_application(db, run.application_id)
            if app_row:
                commission_repository.upsert_projection_for_application(db, app_row)
        except Exception:
            logger.exception("sweep_projection_failed run=%s", run.id)

        if touched:
            recovered += 1
            logger.info("sweep_recovered run=%s new_status=%s", run.id, run_computed.status)

        # Terminal *run* statuses only (do not use TERMINAL_UNIT_STATUSES — those are unit states).
        if run_computed.status in {
            DataCheckRunStatus.ready.value,
            DataCheckRunStatus.partial.value,
            DataCheckRunStatus.failed.value,
        }:
            from invision_api.services.data_check.job_runner_service import _try_auto_advance

            app = data_check_repository.get_application(db, run.application_id)
            _try_auto_advance(db, run_computed=run_computed, app=app, application_id=run.application_id)

        db.flush()

    if skipped_noncanonical > 0:
        logger.info(
            "sweep_noncanonical_summary skipped=%d retired=%d",
            skipped_noncanonical,
            retired_noncanonical,
        )

    return recovered
