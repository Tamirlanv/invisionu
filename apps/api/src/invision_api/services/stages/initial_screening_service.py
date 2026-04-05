"""Initial screening: document extraction, completeness checks, screening result rows."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import Application
from invision_api.models.enums import ApplicationStage, ExtractionStatus, RoleName, ScreeningResult, SectionKey
from invision_api.models.user import Role, User, UserRole
from invision_api.repositories import admissions_repository, document_repository
from invision_api.services import application_service, job_dispatcher_service, text_extraction_service
from invision_api.services.stage_transition_policy import TransitionContext, TransitionName, apply_transition

logger = logging.getLogger(__name__)


def enqueue_post_submit_jobs(
    db: Session,
    application_id: UUID,
    *,
    queue_report: job_dispatcher_service.QueueDispatchReport | None = None,
    strict: bool = False,
) -> job_dispatcher_service.QueueDispatchReport:
    """After submit: queue text extraction for each document and a screening job."""
    report = queue_report or job_dispatcher_service.QueueDispatchReport()
    failed_before = report.failed
    docs = document_repository.list_documents_for_application(db, application_id)
    for d in docs:
        job_dispatcher_service.enqueue_extract_text(
            db,
            application_id,
            d.id,
            queue_report=report,
            strict=strict,
        )
    job_dispatcher_service.enqueue_initial_screening_job(
        db,
        application_id,
        queue_report=report,
        strict=strict,
    )
    failed_delta = report.failed - failed_before
    if failed_delta > 0:
        logger.warning(
            "post_submit_enqueue_degraded application=%s failed_jobs=%s attempted_jobs=%s",
            application_id,
            failed_delta,
            report.attempted,
        )
    return report


def run_extractions_for_application(db: Session, application_id: UUID) -> list[UUID]:
    """Run extraction for every document; returns document ids processed."""
    docs = document_repository.list_documents_for_application(db, application_id)
    out: list[UUID] = []
    for d in docs:
        try:
            text_extraction_service.extract_and_persist_for_document(db, d.id)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "initial_screening_extraction_failed application_id=%s document_id=%s",
                application_id,
                d.id,
            )
            ext = admissions_repository.create_document_extraction(
                db,
                d.id,
                sha256_hex=(d.sha256_hex or ("0" * 64)),
                extracted_text=None,
                extraction_status=ExtractionStatus.failed.value,
                extractor_version=text_extraction_service.EXTRACTOR_VERSION,
                error_message=f"Extraction failed: {exc}",
            )
            admissions_repository.set_document_primary_extraction(db, d.id, ext.id)
        out.append(d.id)
    return out


def _collect_missing_items(db: Session, app: Application) -> dict[str, Any]:
    _, missing = application_service.completion_percentage(db, app)
    return {
        "missing_sections": [m.value for m in missing],
    }


def run_screening_checks_and_record(
    db: Session,
    app: Application,
    *,
    actor_user_id: UUID | None,
) -> Any:
    """Run extraction, evaluate completeness, persist InitialScreeningResult (no automatic transition)."""
    run_extractions_for_application(db, app.id)
    try:
        run_post_submit_content_analysis(db, app)
    except Exception:
        logger.exception("post-submit content analysis failed for app %s", app.id)
    missing = _collect_missing_items(db, app)
    issues: dict[str, Any] = {}
    if missing["missing_sections"]:
        issues["incomplete_sections"] = missing["missing_sections"]

    screening_result = (
        ScreeningResult.passed.value if not issues else ScreeningResult.revision_required.value
    )
    row = admissions_repository.upsert_initial_screening(
        db,
        app.id,
        screening_status="completed",
        missing_items=missing,
        issues_found=issues or None,
        screening_notes=None,
        screening_result=screening_result,
        screening_completed_at=datetime.now(tz=UTC),
    )
    db.flush()
    return row


def apply_screening_transition(
    db: Session,
    app: Application,
    *,
    transition: TransitionName,
    actor_user_id: UUID | None,
    internal_note: str | None = None,
) -> Application:
    if transition not in (TransitionName.screening_passed, TransitionName.revision_required, TransitionName.screening_blocked):
        raise ValueError("invalid screening transition")
    ctx = TransitionContext(
        application_id=app.id,
        transition=transition,
        actor_user_id=actor_user_id,
        actor_type="committee",
        internal_note=internal_note,
    )
    return apply_transition(db, app, ctx)


def ensure_stage(db: Session, app: Application) -> None:
    if app.current_stage != ApplicationStage.initial_screening.value:
        raise ValueError("application must be in initial_screening stage")


def ensure_manual_screening_passed_allowed(db: Session, *, application_id: UUID, user: User) -> None:
    """Reject manual screening_passed unless the data-check pipeline aggregate status is ``ready``.

    Optional break-glass: global admin may bypass when ``allow_screening_passed_bypass_data_check`` is true.
    """
    from invision_api.core.config import get_settings
    from invision_api.services.ai_interview.data_readiness import is_data_processing_ready

    settings = get_settings()
    if settings.allow_screening_passed_bypass_data_check:
        role_names = set(
            db.scalars(
                select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
            ).all()
        )
        if RoleName.admin.value in role_names:
            return

    if is_data_processing_ready(db, application_id):
        return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "DATA_CHECK_NOT_READY",
            "message": (
                "Переход на «Оценку заявки» возможен только после успешного завершения проверки данных "
                "(все блоки обработки в статусе успеха)."
            ),
        },
    )


def run_post_submit_content_analysis(db: Session, app: Application) -> dict[str, Any]:
    """Run definitive content analysis for growth_journey and motivation_goals.

    Called during initial screening after document extraction completes.
    Results are stored with ``source_kind='post_submit'`` for commission use
    and never shown to the candidate.
    """
    results: dict[str, Any] = {}

    section_payloads: dict[str, dict[str, Any]] = {}
    for ss in (app.section_states or []):
        if isinstance(ss.payload, dict):
            section_payloads[ss.section_key] = ss.payload

    growth_raw = section_payloads.get(SectionKey.growth_journey.value)
    if growth_raw:
        try:
            from invision_api.services.section_payloads import GrowthJourneySectionPayload
            from invision_api.services.growth_path.pipeline import run_post_submit_growth_analysis

            validated = GrowthJourneySectionPayload.model_validate(growth_raw)
            results["growth_journey"] = run_post_submit_growth_analysis(db, app.id, validated)
        except Exception:
            logger.exception("post-submit growth analysis failed for app %s", app.id)
            results["growth_journey"] = {"error": "analysis_failed"}

    motivation_raw = section_payloads.get(SectionKey.motivation_goals.value)
    if motivation_raw:
        try:
            narrative = motivation_raw.get("narrative", "")
            word_count = len(narrative.split()) if isinstance(narrative, str) else 0
            char_count = len(narrative) if isinstance(narrative, str) else 0
            was_pasted = motivation_raw.get("was_pasted", False)
            paste_count = motivation_raw.get("paste_count", 0)
            results["motivation_goals"] = {
                "word_count": word_count,
                "char_count": char_count,
                "was_pasted": was_pasted,
                "paste_count": paste_count,
                "has_content": char_count >= 350,
            }

            admissions_repository.create_text_analysis_run(
                db,
                app.id,
                block_key="motivation_goals",
                source_kind="post_submit",
                source_document_id=None,
                model=None,
                status="completed",
                dimensions={
                    "word_count": word_count,
                    "char_count": char_count,
                },
                explanations={
                    "was_pasted": was_pasted,
                    "paste_count": paste_count,
                    "has_content": char_count >= 350,
                },
                flags={"has_llm_summary": False},
            )
        except Exception:
            logger.exception("post-submit motivation analysis failed for app %s", app.id)
            results["motivation_goals"] = {"error": "analysis_failed"}

    return results
