from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.certificate_validation import CertificateValidationResultRow
from invision_api.models.enums import (
    ApplicationStage,
    DataCheckRunStatus,
    DataCheckUnitType,
)
from invision_api.models.link_validation import LinkValidationResultRow
from invision_api.models.video_validation import VideoValidationResultRow
from invision_api.repositories import commission_repository, data_check_repository
from invision_api.services.data_check import orchestrator_service
from invision_api.services.data_check.status_service import compute_run_status


CHECK_ALIAS_TO_UNIT = {
    "links": DataCheckUnitType.link_validation,
    "link_validation": DataCheckUnitType.link_validation,
    "videoPresentation": DataCheckUnitType.video_validation,
    "video_validation": DataCheckUnitType.video_validation,
    "certificates": DataCheckUnitType.certificate_validation,
    "certificate_validation": DataCheckUnitType.certificate_validation,
}


def _normalize_status(value: str) -> str:
    normalized = (value or "").strip().lower()
    mapping = {
        "pending": "pending",
        "queued": "queued",
        "running": "running",
        "completed": "completed",
        "passed": "completed",
        "failed": "failed",
        "error": "failed",
        "manual_review_required": "manual_review_required",
    }
    return mapping.get(normalized, "manual_review_required")


def _persist_typed_results(db: Session, *, application_id: UUID, unit: DataCheckUnitType, result_payload: dict[str, Any]) -> None:
    if unit == DataCheckUnitType.link_validation:
        items = result_payload.get("links")
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            row = LinkValidationResultRow(
                application_id=application_id,
                original_url=str(item.get("originalUrl") or ""),
                normalized_url=item.get("normalizedUrl"),
                is_valid_format=bool(item.get("isValidFormat")),
                is_reachable=bool(item.get("isReachable")),
                availability_status=str(item.get("availabilityStatus") or "unknown"),
                provider=str(item.get("provider") or "unknown"),
                resource_type=str(item.get("resourceType") or "unknown"),
                status_code=item.get("statusCode"),
                content_type=item.get("contentType"),
                content_length=item.get("contentLength"),
                redirected=bool(item.get("redirected")),
                redirect_count=int(item.get("redirectCount") or 0),
                response_time_ms=item.get("responseTimeMs"),
                warnings=[str(v) for v in (item.get("warnings") or [])],
                errors=[str(v) for v in (item.get("errors") or [])],
                confidence=float(item.get("confidence") or 0.0),
            )
            db.add(row)
        db.flush()
        return

    if unit == DataCheckUnitType.video_validation:
        item = result_payload.get("video") if isinstance(result_payload.get("video"), dict) else result_payload
        row = VideoValidationResultRow(
            application_id=application_id,
            video_url=str(item.get("videoUrl") or item.get("url") or ""),
            normalized_url=item.get("normalizedUrl"),
            access_status=str(item.get("accessStatus") or "unknown"),
            media_status=str(item.get("mediaStatus") or "pending_external"),
            duration_sec=item.get("durationSec"),
            width=item.get("width"),
            height=item.get("height"),
            has_video_track=bool(item.get("hasVideoTrack")),
            has_audio_track=bool(item.get("hasAudioTrack")),
            codec_video=item.get("codecVideo"),
            codec_audio=item.get("codecAudio"),
            total_frames_analyzed=int(item.get("totalFramesAnalyzed") or 0),
            face_detected_frames_count=int(item.get("faceDetectedFramesCount") or 0),
            face_coverage_ratio=float(item.get("faceCoverageRatio") or 0.0),
            average_face_confidence=item.get("averageFaceConfidence"),
            sampled_timestamps_sec=[float(v) for v in (item.get("sampledTimestampsSec") or [])],
            has_speech=bool(item.get("hasSpeech")),
            speech_segment_count=int(item.get("speechSegmentCount") or 0),
            speech_coverage_ratio=item.get("speechCoverageRatio"),
            transcript_preview=item.get("transcriptPreview"),
            transcript_confidence=item.get("transcriptConfidence"),
            likely_face_visible=bool(item.get("likelyFaceVisible")),
            likely_speech_audible=bool(item.get("likelySpeechAudible")),
            likely_presentation_valid=bool(item.get("likelyPresentationValid")),
            manual_review_required=bool(item.get("manualReviewRequired")),
            explainability=[str(v) for v in (item.get("explainability") or [])],
            warnings=[str(v) for v in (item.get("warnings") or [])],
            errors=[str(v) for v in (item.get("errors") or [])],
            confidence=float(item.get("confidence") or 0.0),
            summary_text=item.get("summaryText"),
        )
        db.add(row)
        db.flush()
        return

    if unit == DataCheckUnitType.certificate_validation:
        items = result_payload.get("certificates")
        if not isinstance(items, list):
            items = [result_payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            row = CertificateValidationResultRow(
                application_id=application_id,
                document_type=str(item.get("documentType") or "education_certificate"),
                processing_status=str(item.get("processingStatus") or "completed"),
                extracted_fields=item.get("extractedFields"),
                threshold_checks=item.get("thresholdChecks"),
                authenticity_status=str(item.get("authenticityStatus") or "manual_review_required"),
                template_match_score=item.get("templateMatchScore"),
                ocr_confidence=item.get("ocrConfidence"),
                fraud_signals=[str(v) for v in (item.get("fraudSignals") or [])],
                warnings=[str(v) for v in (item.get("warnings") or [])],
                errors=[str(v) for v in (item.get("errors") or [])],
                explainability=[str(v) for v in (item.get("explainability") or [])],
                confidence=float(item.get("confidence") or 0.0),
                summary_text=item.get("summaryText"),
            )
            db.add(row)
        db.flush()


def _stage_from_run_status(run_status: str) -> str:
    if run_status in {DataCheckRunStatus.pending.value, DataCheckRunStatus.running.value}:
        return "in_review"
    if run_status == DataCheckRunStatus.ready.value:
        return "approved"
    return "needs_attention"


def ingest_external_unit_result(
    db: Session,
    *,
    application_id: UUID,
    run_id: UUID,
    check_type: str,
    status: str,
    result_payload: dict[str, Any],
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    explainability: list[str] | None = None,
) -> None:
    unit = CHECK_ALIAS_TO_UNIT.get(check_type)
    if not unit:
        return
    run = data_check_repository.get_run(db, run_id)
    if not run:
        return
    check = data_check_repository.get_check(db, run_id, unit.value)
    if not check:
        return

    unit_status = _normalize_status(status)
    now = datetime.now(tz=UTC)
    data_check_repository.update_check_status(
        db,
        check=check,
        status=unit_status,
        result_payload=result_payload,
        last_error="; ".join(errors or []) if errors else None,
    )
    data_check_repository.upsert_unit_result(
        db,
        run_id=run_id,
        application_id=application_id,
        unit_type=unit.value,
        status=unit_status,
        result_payload=result_payload,
        warnings=warnings or [],
        errors=errors or [],
        explainability=explainability or [],
        manual_review_required=unit_status == "manual_review_required",
        attempts=check.attempts,
        started_at=check.started_at or now,
        finished_at=check.finished_at or now,
    )
    _persist_typed_results(db, application_id=application_id, unit=unit, result_payload=result_payload)

    checks = data_check_repository.list_checks_for_run(db, run_id)
    status_map = {}
    for c in checks:
        try:
            status_map[DataCheckUnitType(c.check_type)] = c.status
        except ValueError:
            continue
    computed = compute_run_status(status_map)
    data_check_repository.update_run_status(
        db,
        run=run,
        status=computed.status,
        warnings=computed.warnings,
        errors=computed.errors,
        explainability=computed.explainability,
    )
    commission_repository.set_stage_status(
        db,
        application_id=application_id,
        stage=ApplicationStage.initial_screening.value,
        status=_stage_from_run_status(computed.status),
        actor_user_id=None,
        reason_comment=f"External data-check ingestion: {unit.value}",
    )
    commission_repository.set_attention_flag(
        db,
        application_id=application_id,
        stage=ApplicationStage.initial_screening.value,
        value=computed.manual_review_required,
    )
    app = data_check_repository.get_application(db, application_id)
    if app:
        commission_repository.upsert_projection_for_application(db, app)
    orchestrator_service.enqueue_ready_followup_jobs(db, application_id=application_id, run_id=run_id)
