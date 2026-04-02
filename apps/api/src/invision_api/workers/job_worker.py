"""Process one job from the Redis admission queue (LPOP). Intended for a separate worker process."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from invision_api.core.redis_client import get_redis_client
from invision_api.db.session import SessionLocal
from invision_api.models.enums import DataCheckUnitType, JobType
from invision_api.services.data_check import job_runner_service
from invision_api.services.job_dispatcher_service import QUEUE_NAME
from invision_api.services import text_extraction_service
from invision_api.services.stages import initial_screening_service


def process_payload(payload: dict[str, Any]) -> None:
    job_type = payload.get("job_type")
    app_id = UUID(payload["application_id"])
    analysis_job_id = UUID(payload["analysis_job_id"]) if payload.get("analysis_job_id") else None
    db = SessionLocal()
    try:
        if job_type == JobType.extract_text.value:
            doc_id = UUID(payload["document_id"])
            text_extraction_service.extract_and_persist_for_document(db, doc_id)
            db.commit()
        elif job_type == JobType.initial_screening.value:
            from invision_api.repositories import admissions_repository

            app = admissions_repository.get_application_by_id(db, app_id)
            if app:
                initial_screening_service.run_screening_checks_and_record(db, app, actor_user_id=None)
                db.commit()
        elif job_type == JobType.run_block_analysis.value:
            # Analysis jobs are processed by a dedicated handler or deferred.
            db.commit()
        elif job_type == JobType.data_check_unit.value:
            run_id = UUID(payload["run_id"])
            unit_type = DataCheckUnitType(payload["unit_type"])
            job_runner_service.run_unit(
                db,
                application_id=app_id,
                run_id=run_id,
                unit_type=unit_type,
                analysis_job_id=analysis_job_id,
            )
            db.commit()
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
