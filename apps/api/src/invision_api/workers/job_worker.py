"""Process one job from the Redis admission queue (LPOP). Intended for a separate worker process."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.core.redis_client import get_redis_client
from invision_api.db.session import SessionLocal
from invision_api.models.enums import DataCheckUnitType, JobStatus, JobType
from invision_api.repositories import admissions_repository
from invision_api.services import candidate_stage_email_service
from invision_api.services.data_check import job_runner_service
from invision_api.services.job_dispatcher_service import QUEUE_NAME
from invision_api.services import text_extraction_service
from invision_api.services.stages import initial_screening_service

logger = logging.getLogger(__name__)

_TERMINAL_ANALYSIS_JOB_STATUSES = {
    JobStatus.completed.value,
    JobStatus.failed.value,
    JobStatus.dead.value,
}


def _mark_analysis_job_failed(db: Session, analysis_job_id: UUID | None, *, reason_code: str) -> None:
    if not analysis_job_id:
        return
    job_row = admissions_repository.get_analysis_job(db, analysis_job_id)
    if not job_row:
        return
    admissions_repository.update_analysis_job(
        db,
        job_row,
        status=JobStatus.failed.value,
        attempts=(job_row.attempts or 0) + 1,
        last_error=reason_code[:500],
    )


def process_payload(payload: dict[str, Any]) -> None:
    job_type = payload.get("job_type")
    app_id = UUID(payload["application_id"])
    analysis_job_id = UUID(payload["analysis_job_id"]) if payload.get("analysis_job_id") else None
    db = SessionLocal()
    try:
        if job_type == JobType.extract_text.value:
            doc_id = UUID(payload["document_id"])
            analysis_job = (
                admissions_repository.get_analysis_job(db, analysis_job_id)
                if analysis_job_id
                else None
            )
            if analysis_job and analysis_job.status in _TERMINAL_ANALYSIS_JOB_STATUSES:
                logger.info(
                    "extract_text_skip_terminal_analysis_job application=%s analysis_job_id=%s status=%s",
                    app_id,
                    analysis_job_id,
                    analysis_job.status,
                )
                db.commit()
                return
            if analysis_job:
                admissions_repository.update_analysis_job(
                    db,
                    analysis_job,
                    status=JobStatus.running.value,
                    attempts=(analysis_job.attempts or 0) + 1,
                )

            app = admissions_repository.get_application_by_id(db, app_id)
            if not app:
                reason = f"stale_application_context:application_not_found:{app_id}"
                _mark_analysis_job_failed(db, analysis_job_id, reason_code=reason)
                logger.warning(
                    "extract_text_stale_application_context application=%s analysis_job_id=%s document_id=%s",
                    app_id,
                    analysis_job_id,
                    doc_id,
                )
                db.commit()
                return

            try:
                text_extraction_service.extract_and_persist_for_document(db, doc_id)
            except text_extraction_service.DocumentNotFoundError:
                reason = f"stale_document_not_found:{doc_id}"
                _mark_analysis_job_failed(db, analysis_job_id, reason_code=reason)
                logger.warning(
                    "extract_text_stale_document application=%s analysis_job_id=%s document_id=%s",
                    app_id,
                    analysis_job_id,
                    doc_id,
                )
                db.commit()
                return
            except Exception as exc:  # noqa: BLE001
                reason = f"extract_text_exception:{str(exc)[:300]}"
                _mark_analysis_job_failed(db, analysis_job_id, reason_code=reason)
                logger.exception(
                    "extract_text_job_failed application=%s analysis_job_id=%s document_id=%s",
                    app_id,
                    analysis_job_id,
                    doc_id,
                )
                db.commit()
                return

            if analysis_job_id:
                analysis_job = admissions_repository.get_analysis_job(db, analysis_job_id)
                if analysis_job:
                    admissions_repository.update_analysis_job(
                        db,
                        analysis_job,
                        status=JobStatus.completed.value,
                    )
            db.commit()
        elif job_type == JobType.initial_screening.value:
            app = admissions_repository.get_application_by_id(db, app_id)
            if app:
                initial_screening_service.run_screening_checks_and_record(db, app, actor_user_id=None)
                db.commit()
        elif job_type == JobType.run_block_analysis.value:
            # No block-level LLM pipeline yet; mark job completed so queues do not stall.
            if analysis_job_id:
                job_row = admissions_repository.get_analysis_job(db, analysis_job_id)
                if job_row:
                    admissions_repository.update_analysis_job(
                        db,
                        job_row,
                        status=JobStatus.completed.value,
                        last_error=None,
                    )
            db.commit()
        elif job_type == JobType.data_check_unit.value:
            run_id = UUID(payload["run_id"])
            unit_type = DataCheckUnitType(payload["unit_type"])
            app_before = admissions_repository.get_application_by_id(db, app_id)
            prev_stage = app_before.current_stage if app_before else None
            job_runner_service.run_unit(
                db,
                application_id=app_id,
                run_id=run_id,
                unit_type=unit_type,
                analysis_job_id=analysis_job_id,
            )
            db.commit()
            if prev_stage is not None:
                app_after = admissions_repository.get_application_by_id(db, app_id)
                if app_after and app_after.current_stage != prev_stage:
                    candidate_stage_email_service.send_stage_transition_notification(
                        app_id, prev_stage, app_after.current_stage
                    )
        else:
            db.rollback()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def pop_and_run_one() -> bool:
    """Return True if a job was processed."""
    r = get_redis_client()
    raw = r.rpop(QUEUE_NAME)
    if not raw:
        return False
    payload = json.loads(raw)
    process_payload(payload)
    return True
