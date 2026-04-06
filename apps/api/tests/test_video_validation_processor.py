from __future__ import annotations

from sqlalchemy.orm import Session

from invision_api.models.video_validation import VideoValidationResultRow
from invision_api.services.data_check.processors.video_validation_processor import run_video_validation_processing
from invision_api.services.video_processing.pipeline import VideoPipelineOutcome


def _partial_outcome() -> VideoPipelineOutcome:
    return VideoPipelineOutcome(
        provider="dropbox",
        resource_type="video",
        ingestion_strategy="dropbox_direct_download",
        normalized_url="https://www.dropbox.com/s/abc/presentation.mp4?dl=1",
        access_status="reachable",
        duration_sec=299,
        duration_formatted="4:59",
        width=1280,
        height=720,
        codec_video="h264",
        codec_audio="aac",
        container="mov,mp4,m4a,3gp,3g2,mj2",
        has_video_track=True,
        has_audio_track=True,
        sampled_timestamps_sec=[10.0, 30.0, 50.0, 70.0, 90.0, 110.0],
        frames_extracted_success=6,
        face_detected_frames_count=1,
        raw_transcript="Короткий пример транскрипта",
        transcript_source="none",
        transcript_confidence=None,
        captions_language=None,
        text_acquisition_error_code="asr_unavailable",
        commission_summary="Текст не обнаружен",
        candidate_visible=True,
        has_speech=False,
        warnings=[],
        errors=["Недостаточно качества звука для стабильной транскрибации."],
        media_status="partial",
    )


def _asr_partial_outcome() -> VideoPipelineOutcome:
    return VideoPipelineOutcome(
        provider="youtube",
        resource_type="video",
        ingestion_strategy="youtube_ytdlp",
        normalized_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        access_status="reachable",
        duration_sec=213,
        duration_formatted="3:33",
        width=1280,
        height=720,
        codec_video="h264",
        codec_audio="aac",
        container="mp4",
        has_video_track=True,
        has_audio_track=True,
        sampled_timestamps_sec=[10.0, 30.0, 50.0, 70.0, 90.0, 110.0],
        frames_extracted_success=6,
        face_detected_frames_count=3,
        raw_transcript="",
        transcript_source="none",
        transcript_confidence=None,
        captions_language=None,
        text_acquisition_error_code="asr_unavailable",
        commission_summary="Текст не обнаружен",
        candidate_visible=True,
        has_speech=False,
        warnings=["Транскрибация недоступна: ASR недоступен: timeout"],
        errors=[],
        media_status="partial",
    )


def _youtube_too_long_outcome() -> VideoPipelineOutcome:
    return VideoPipelineOutcome(
        provider="youtube",
        resource_type="video",
        ingestion_strategy="youtube_ytdlp",
        normalized_url="https://www.youtube.com/watch?v=too_long",
        access_status="reachable",
        duration_sec=401,
        duration_formatted="6:41",
        width=1280,
        height=720,
        codec_video="h264",
        codec_audio="aac",
        container="mp4",
        has_video_track=True,
        has_audio_track=True,
        sampled_timestamps_sec=[],
        frames_extracted_success=0,
        face_detected_frames_count=0,
        raw_transcript="",
        transcript_source="none",
        transcript_confidence=None,
        captions_language=None,
        text_acquisition_error_code=None,
        commission_summary="Видео длиннее 6 минут",
        candidate_visible=False,
        has_speech=False,
        warnings=[],
        errors=[],
        media_status="ready",
    )


def test_video_validation_processor_persists_extended_payload_and_manual_state(
    db: Session, factory, monkeypatch
) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    factory.fill_required_sections(db, app)

    monkeypatch.setattr(
        "invision_api.services.data_check.processors.video_validation_processor.run_presentation_pipeline",
        lambda _url: _partial_outcome(),
    )

    result = run_video_validation_processing(db, application_id=app.id, candidate_id=profile.id)
    db.flush()

    assert result.status == "manual_review_required"
    assert result.payload is not None
    assert result.payload["provider"] == "dropbox"
    assert result.payload["resourceType"] == "video"
    assert result.payload["ingestionStrategy"] == "dropbox_direct_download"
    assert result.payload["durationSec"] == 299
    assert result.payload["transcriptSource"] == "none"
    assert result.payload["textAcquisitionErrorCode"] == "asr_unavailable"

    row = (
        db.query(VideoValidationResultRow)
        .filter(VideoValidationResultRow.application_id == app.id)
        .order_by(VideoValidationResultRow.created_at.desc())
        .first()
    )
    assert row is not None
    assert row.normalized_url == "https://www.dropbox.com/s/abc/presentation.mp4?dl=1"
    assert row.media_status == "partial"
    assert row.manual_review_required is True
    assert row.codec_video == "h264"
    assert row.codec_audio == "aac"


def test_video_validation_processor_marks_asr_partial_with_error_code(db: Session, factory, monkeypatch) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    factory.fill_required_sections(db, app)

    monkeypatch.setattr(
        "invision_api.services.data_check.processors.video_validation_processor.run_presentation_pipeline",
        lambda _url: _asr_partial_outcome(),
    )

    result = run_video_validation_processing(db, application_id=app.id, candidate_id=profile.id)
    db.flush()

    assert result.status == "manual_review_required"
    assert result.payload is not None
    assert result.payload["mediaStatus"] == "partial"
    assert result.payload["errorCode"] == "asr_unavailable"
    assert result.payload["textAcquisitionErrorCode"] == "asr_unavailable"


def test_video_validation_processor_marks_youtube_too_long_as_completed(db: Session, factory, monkeypatch) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    factory.fill_required_sections(db, app)

    monkeypatch.setattr(
        "invision_api.services.data_check.processors.video_validation_processor.run_presentation_pipeline",
        lambda _url: _youtube_too_long_outcome(),
    )

    result = run_video_validation_processing(db, application_id=app.id, candidate_id=profile.id)
    assert result.status == "completed"
    assert result.payload is not None
    assert result.payload["mediaStatus"] == "ready"
    assert result.payload["summary"] == "Видео длиннее 6 минут"
