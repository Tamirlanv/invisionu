from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.enums import SectionKey
from invision_api.models.video_validation import VideoValidationResultRow
from invision_api.services.data_check.adapters.validation_orchestrator_client import ValidationOrchestratorClient
from invision_api.services.data_check.contracts import UnitExecutionResult
from invision_api.services.data_check.utils import get_validated_section


def run_video_validation_processing(db: Session, *, application_id: UUID, candidate_id: UUID) -> UnitExecutionResult:
    validated = get_validated_section(
        db,
        application_id=application_id,
        section_key=SectionKey.education,
    )
    video_url = ""
    if validated and validated.presentation_video_url:
        video_url = validated.presentation_video_url.strip()

    orchestrator_run_id = None
    orchestrator_warning = None
    client = ValidationOrchestratorClient()
    try:
        created = client.create_run(
            application_id=application_id,
            candidate_id=candidate_id,
            checks=["videoPresentation"],
        )
        orchestrator_run_id = (created or {}).get("runId")
    except Exception:  # noqa: BLE001
        orchestrator_warning = "External orchestrator unavailable for video validation."

    if not video_url:
        return UnitExecutionResult(
            status="manual_review_required",
            payload={"externalRunId": orchestrator_run_id, "videoUrl": None},
            warnings=[orchestrator_warning] if orchestrator_warning else [],
            explainability=["Не указан URL видеопрезентации, нужен ручной разбор."],
            manual_review_required=True,
        )

    is_http = video_url.startswith("http://") or video_url.startswith("https://")
    manual = bool(orchestrator_warning or not is_http)
    row = VideoValidationResultRow(
        application_id=application_id,
        video_url=video_url,
        normalized_url=video_url if is_http else None,
        access_status="reachable" if is_http else "invalid",
        media_status="pending_external" if is_http else "processing_failed",
        has_video_track=False,
        has_audio_track=False,
        likely_face_visible=False,
        likely_speech_audible=False,
        likely_presentation_valid=is_http,
        manual_review_required=manual,
        explainability=[
            "Базовая локальная проверка URL выполнена.",
            "Подробные медиасигналы ожидаются от внешнего orchestrator.",
        ],
        warnings=[orchestrator_warning] if orchestrator_warning else [],
        errors=[] if is_http else ["Invalid video URL format"],
        confidence=0.2 if is_http else 0.0,
        summary_text="External validation pending." if is_http else "Invalid video URL.",
    )
    db.add(row)
    db.flush()

    return UnitExecutionResult(
        status="manual_review_required" if manual else "completed",
        payload={
            "externalRunId": orchestrator_run_id,
            "resultId": str(row.id),
            "videoUrl": video_url,
            "accessStatus": row.access_status,
            "mediaStatus": row.media_status,
        },
        warnings=[orchestrator_warning] if orchestrator_warning else [],
        explainability=row.explainability or [],
        manual_review_required=manual,
    )
