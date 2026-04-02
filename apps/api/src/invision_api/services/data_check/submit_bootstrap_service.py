from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.enums import ApplicationStage, DataCheckRunStatus, DataCheckUnitStatus, DataCheckUnitType
from invision_api.repositories import commission_repository, data_check_repository
from invision_api.services import job_dispatcher_service
from invision_api.services.data_check import orchestrator_service

logger = logging.getLogger(__name__)


def _build_snapshot_payload(db: Session, *, application_id: UUID) -> dict:
    section_states = data_check_repository.list_section_states(db, application_id)
    answers = data_check_repository.list_internal_test_answers(db, application_id)
    documents = data_check_repository.list_documents(db, application_id)
    return {
        "sections": {
            s.section_key: {
                "is_complete": s.is_complete,
                "schema_version": s.schema_version,
                "last_saved_at": s.last_saved_at.isoformat() if s.last_saved_at else None,
                "payload": s.payload,
            }
            for s in section_states
        },
        "internal_test_answers": [
            {
                "question_id": str(a.question_id),
                "selected_options": a.selected_options,
                "text_answer": a.text_answer,
                "is_finalized": a.is_finalized,
                "saved_at": a.saved_at.isoformat() if a.saved_at else None,
            }
            for a in answers
        ],
        "documents": [
            {
                "id": str(d.id),
                "document_type": d.document_type,
                "verification_status": d.verification_status,
                "byte_size": d.byte_size,
                "sha256_hex": d.sha256_hex,
            }
            for d in documents
        ],
        "captured_at": datetime.now(tz=UTC).isoformat(),
    }


def bootstrap_data_check_pipeline(
    db: Session,
    *,
    application_id: UUID,
    candidate_id: UUID,
    actor_user_id: UUID | None,
    queue_report: job_dispatcher_service.QueueDispatchReport | None = None,
    strict: bool = False,
) -> UUID:
    runs = data_check_repository.list_runs_for_application(db, application_id)
    if runs and runs[0].overall_status in {
        DataCheckRunStatus.pending.value,
        DataCheckRunStatus.running.value,
    }:
        return runs[0].id

    app = data_check_repository.get_application(db, application_id)
    submitted_at = app.submitted_at if app else datetime.now(tz=UTC)

    data_check_repository.upsert_submission_snapshot(
        db,
        application_id=application_id,
        candidate_id=candidate_id,
        snapshot_kind="submitted",
        payload=_build_snapshot_payload(db, application_id=application_id),
        submitted_at=submitted_at,
    )

    run = data_check_repository.create_run(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
        status=DataCheckRunStatus.pending.value,
        explainability=["Data-check pipeline bootstrapped from submitted snapshot."],
    )
    for unit in DataCheckUnitType:
        data_check_repository.create_check(
            db,
            run_id=run.id,
            check_type=unit.value,
            status=DataCheckUnitStatus.pending.value,
            result_payload=None,
        )
        data_check_repository.upsert_unit_result(
            db,
            run_id=run.id,
            application_id=application_id,
            unit_type=unit.value,
            status=DataCheckUnitStatus.pending.value,
            result_payload=None,
            warnings=[],
            errors=[],
            explainability=[],
            manual_review_required=False,
            attempts=0,
            started_at=None,
            finished_at=None,
        )

    report = queue_report or job_dispatcher_service.QueueDispatchReport()
    failed_before = report.failed
    orchestrator_service.enqueue_first_wave_jobs(
        db,
        application_id=application_id,
        run_id=run.id,
        queue_report=report,
        strict=strict,
    )
    failed_delta = report.failed - failed_before
    if failed_delta > 0:
        logger.warning(
            "data_check_bootstrap_enqueue_degraded application=%s run_id=%s failed_jobs=%s attempted_jobs=%s",
            application_id,
            run.id,
            failed_delta,
            report.attempted,
        )

    commission_repository.set_stage_status(
        db,
        application_id=application_id,
        stage=ApplicationStage.initial_screening.value,
        status="new",
        actor_user_id=actor_user_id,
        reason_comment="DATA_CHECK pipeline initialized.",
    )
    app = data_check_repository.get_application(db, application_id)
    if app:
        commission_repository.upsert_projection_for_application(db, app)
    return run.id
