from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.enums import SectionKey
from invision_api.models.video_validation import VideoValidationResultRow
from invision_api.services.data_check.contracts import UnitExecutionResult
from invision_api.services.data_check.utils import get_validated_section
from invision_api.services.video_processing import run_presentation_pipeline
from invision_api.services.video_processing.constants import MEDIA_STATUS_FAILED, MEDIA_STATUS_PARTIAL, MEDIA_STATUS_READY

logger = logging.getLogger(__name__)


def _detect_video_error_code(errors: list[str], warnings: list[str] | None = None) -> str | None:
    blob = " ".join((e or "") for e in errors).lower()
    if warnings:
        blob = f"{blob} {' '.join((w or '') for w in warnings).lower()}"
    if not blob:
        return None
    if "транскрибация недоступна" in blob or "asr" in blob:
        return "asr_unavailable"
    if "субтитры youtube недоступны" in blob or "captions" in blob:
        if "429" in blob or "rate" in blob:
            return "captions_rate_limited"
        return "captions_unavailable"
    if "суммаризация недоступна" in blob:
        return "summary_unavailable"
    if "yt-dlp" in blob or "yt_dlp" in blob:
        return "missing_ytdlp"
    if "ffprobe" in blob and "не найден бинарник" in blob:
        return "missing_ffprobe"
    if "ffmpeg" in blob and "не найден бинарник" in blob:
        return "missing_ffmpeg"
    if "таймаут" in blob:
        return "media_tool_timeout"
    if "метаданные" in blob:
        return "probe_failed"
    if "загрузить видео" in blob:
        return "ingestion_failed"
    return "video_processing_error"


def run_video_validation_processing(db: Session, *, application_id: UUID, candidate_id: UUID) -> UnitExecutionResult:
    _ = candidate_id
    validated = get_validated_section(
        db,
        application_id=application_id,
        section_key=SectionKey.education,
    )
    video_url = ""
    if validated and validated.presentation_video_url:
        video_url = validated.presentation_video_url.strip()

    if not video_url:
        return UnitExecutionResult(
            status="manual_review_required",
            payload={"videoUrl": None},
            warnings=[],
            explainability=["Не указан URL видеопрезентации."],
            manual_review_required=True,
        )

    try:
        outcome = run_presentation_pipeline(video_url)
    except Exception:
        logger.exception("video pipeline crashed application_id=%s", application_id)
        row = VideoValidationResultRow(
            application_id=application_id,
            video_url=video_url,
            normalized_url=video_url,
            access_status="unreachable",
            media_status=MEDIA_STATUS_FAILED,
            codec_video=None,
            codec_audio=None,
            errors=["Внутренняя ошибка обработки видео."],
            manual_review_required=True,
            summary_text=None,
        )
        db.add(row)
        db.flush()
        return UnitExecutionResult(
            status="failed",
            payload={"resultId": str(row.id), "videoUrl": video_url, "errorCode": "video_pipeline_exception"},
            errors=["Внутренняя ошибка обработки видео."],
            explainability=["Исключение при выполнении пайплайна видео."],
            manual_review_required=True,
        )

    ok = outcome.media_status == MEDIA_STATUS_READY and not outcome.errors
    partial = outcome.media_status == MEDIA_STATUS_PARTIAL
    manual = not ok
    if ok:
        unit_status = "completed"
    elif partial:
        unit_status = "manual_review_required"
    else:
        unit_status = "failed"

    analyzed = outcome.frames_extracted_success
    error_code = _detect_video_error_code(list(outcome.errors), list(outcome.warnings))
    effective_error_code = outcome.text_acquisition_error_code or error_code
    row = VideoValidationResultRow(
        application_id=application_id,
        video_url=video_url,
        normalized_url=outcome.normalized_url or video_url,
        access_status=outcome.access_status or ("reachable" if outcome.media_status != MEDIA_STATUS_FAILED else "unreachable"),
        media_status=outcome.media_status,
        duration_sec=outcome.duration_sec,
        width=outcome.width,
        height=outcome.height,
        has_video_track=outcome.has_video_track,
        has_audio_track=outcome.has_audio_track,
        codec_video=outcome.codec_video,
        codec_audio=outcome.codec_audio,
        total_frames_analyzed=analyzed,
        face_detected_frames_count=outcome.face_detected_frames_count,
        face_coverage_ratio=(outcome.face_detected_frames_count / analyzed) if analyzed else 0.0,
        sampled_timestamps_sec=outcome.sampled_timestamps_sec,
        has_speech=outcome.has_speech,
        speech_segment_count=1 if outcome.has_speech else 0,
        transcript_preview=outcome.raw_transcript or None,
        transcript_confidence=outcome.transcript_confidence,
        likely_face_visible=outcome.candidate_visible,
        likely_speech_audible=outcome.has_speech,
        likely_presentation_valid=ok,
        manual_review_required=manual,
        explainability=[
            "Видеопрезентация обработана.",
            f"Источник: {outcome.provider}",
            f"Стратегия загрузки: {outcome.ingestion_strategy}",
            f"Источник транскрипта: {outcome.transcript_source}",
            f"Язык субтитров: {outcome.captions_language}" if outcome.captions_language else "Язык субтитров: -",
        ],
        warnings=outcome.warnings,
        errors=list(outcome.errors),
        confidence=0.85 if ok else 0.35,
        summary_text=outcome.commission_summary,
    )
    db.add(row)
    db.flush()

    return UnitExecutionResult(
        status=unit_status,
        payload={
            "resultId": str(row.id),
            "videoUrl": video_url,
            "normalizedUrl": row.normalized_url,
            "provider": outcome.provider,
            "resourceType": outcome.resource_type,
            "ingestionStrategy": outcome.ingestion_strategy,
            "mediaStatus": row.media_status,
            "accessStatus": row.access_status,
            "durationSec": row.duration_sec,
            "codecVideo": row.codec_video,
            "codecAudio": row.codec_audio,
            "container": outcome.container,
            "candidateVisible": outcome.candidate_visible,
            "summary": row.summary_text,
            "transcriptSource": outcome.transcript_source,
            "captionsLanguage": outcome.captions_language,
            "textAcquisitionErrorCode": outcome.text_acquisition_error_code,
            "errorCode": effective_error_code,
        },
        warnings=outcome.warnings,
        errors=list(outcome.errors),
        explainability=row.explainability or [],
        manual_review_required=manual,
    )
