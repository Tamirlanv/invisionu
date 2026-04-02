"""Enqueue background jobs (Redis list) and persist AnalysisJob rows."""

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.core.redis_client import enqueue_job
from invision_api.models.enums import DataCheckUnitType, JobStatus, JobType
from invision_api.repositories import admissions_repository

QUEUE_NAME = "invision:admission_jobs"
logger = logging.getLogger(__name__)


class QueueDispatchError(RuntimeError):
    def __init__(
        self,
        *,
        context: str,
        application_id: UUID,
        analysis_job_id: UUID,
        error_text: str,
    ) -> None:
        self.context = context
        self.application_id = application_id
        self.analysis_job_id = analysis_job_id
        self.error_text = error_text
        super().__init__(f"queue enqueue failed for {context}: {error_text}")


@dataclass(slots=True)
class QueueDispatchReport:
    attempted: int = 0
    enqueued: int = 0
    failed: int = 0
    failures: list[dict[str, str]] = field(default_factory=list)

    @property
    def queue_status(self) -> str:
        return "degraded" if self.failed else "ready"

    @property
    def queue_message(self) -> str | None:
        if not self.failed:
            return None
        if self.failed == 1:
            return "Анкета отправлена, но один фоновый шаг поставлен в очередь с ошибкой. Обработка продолжится после восстановления сервиса."
        return (
            f"Анкета отправлена, но {self.failed} фоновых шагов поставлены в очередь с ошибкой. "
            "Обработка продолжится после восстановления сервиса."
        )


def _enqueue_with_fallback(
    db: Session,
    *,
    job: Any,
    payload: dict[str, Any],
    context: str,
    queue_report: QueueDispatchReport | None = None,
    log_failure: bool = True,
    raise_on_failure: bool = False,
) -> bool:
    if queue_report is not None:
        queue_report.attempted += 1
    try:
        enqueue_job(QUEUE_NAME, payload)
        if queue_report is not None:
            queue_report.enqueued += 1
        return True
    except Exception as exc:  # noqa: BLE001
        error_text = str(exc)
        admissions_repository.update_analysis_job(
            db,
            job,
            status=JobStatus.failed.value,
            attempts=(job.attempts or 0) + 1,
            last_error=f"queue_enqueue_failed: {error_text}",
        )
        if queue_report is not None:
            queue_report.failed += 1
            queue_report.failures.append(
                {
                    "jobType": context,
                    "applicationId": str(job.application_id),
                    "analysisJobId": str(job.id),
                    "error": error_text[:240],
                }
            )
        if log_failure:
            logger.warning(
                "queue_enqueue_failed application=%s job_type=%s analysis_job_id=%s error=%s",
                job.application_id,
                context,
                job.id,
                error_text,
            )
        if raise_on_failure:
            raise QueueDispatchError(
                context=context,
                application_id=job.application_id,
                analysis_job_id=job.id,
                error_text=error_text,
            ) from exc
        return False


def enqueue_extract_text(
    db: Session,
    application_id: UUID,
    document_id: UUID,
    *,
    queue_report: QueueDispatchReport | None = None,
    strict: bool = False,
) -> UUID:
    job = admissions_repository.create_analysis_job(
        db,
        application_id,
        job_type=JobType.extract_text.value,
        payload={"document_id": str(document_id)},
        status=JobStatus.queued.value,
    )
    db.flush()
    _enqueue_with_fallback(
        db,
        job=job,
        context=JobType.extract_text.value,
        payload={
            "job_type": JobType.extract_text.value,
            "analysis_job_id": str(job.id),
            "application_id": str(application_id),
            "document_id": str(document_id),
        },
        queue_report=queue_report,
        log_failure=queue_report is None or strict,
        raise_on_failure=strict,
    )
    return job.id


def enqueue_run_block_analysis(
    db: Session,
    application_id: UUID,
    *,
    block_key: str,
    source_document_id: UUID | None = None,
    strict: bool = False,
) -> None:
    payload: dict[str, Any] = {"block_key": block_key}
    if source_document_id:
        payload["source_document_id"] = str(source_document_id)
    job = admissions_repository.create_analysis_job(
        db,
        application_id,
        job_type=JobType.run_block_analysis.value,
        payload=payload,
        status=JobStatus.queued.value,
    )
    db.flush()
    _enqueue_with_fallback(
        db,
        job=job,
        context=JobType.run_block_analysis.value,
        payload={
            "job_type": JobType.run_block_analysis.value,
            "analysis_job_id": str(job.id),
            "application_id": str(application_id),
            **payload,
        },
        raise_on_failure=strict,
    )


def enqueue_initial_screening_job(
    db: Session,
    application_id: UUID,
    *,
    queue_report: QueueDispatchReport | None = None,
    strict: bool = False,
) -> UUID:
    job = admissions_repository.create_analysis_job(
        db,
        application_id,
        job_type=JobType.initial_screening.value,
        payload={},
        status=JobStatus.queued.value,
    )
    db.flush()
    _enqueue_with_fallback(
        db,
        job=job,
        context=JobType.initial_screening.value,
        payload={
            "job_type": JobType.initial_screening.value,
            "analysis_job_id": str(job.id),
            "application_id": str(application_id),
        },
        queue_report=queue_report,
        log_failure=queue_report is None or strict,
        raise_on_failure=strict,
    )
    return job.id


def enqueue_data_check_unit_job(
    db: Session,
    *,
    application_id: UUID,
    run_id: UUID,
    unit_type: DataCheckUnitType,
    queue_report: QueueDispatchReport | None = None,
    strict: bool = False,
) -> UUID:
    payload = {"run_id": str(run_id), "unit_type": unit_type.value}
    job = admissions_repository.create_analysis_job(
        db,
        application_id,
        job_type=JobType.data_check_unit.value,
        payload=payload,
        status=JobStatus.queued.value,
    )
    db.flush()
    payload = {
        "job_type": JobType.data_check_unit.value,
        "analysis_job_id": str(job.id),
        "application_id": str(application_id),
        "run_id": str(run_id),
        "unit_type": unit_type.value,
    }
    _enqueue_with_fallback(
        db,
        job=job,
        context=JobType.data_check_unit.value,
        payload=payload,
        queue_report=queue_report,
        log_failure=queue_report is None or strict,
        raise_on_failure=strict,
    )
    return job.id
