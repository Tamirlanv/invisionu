from __future__ import annotations

import logging
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from invision_api.services.video_processing import ffmpeg_tools
from invision_api.services.link_validation.service import validate_presentation_video_only
from invision_api.services.video_processing.constants import (
    COMMISSION_NO_TEXT,
    MAX_AUDIO_FOR_TRANSCRIPTION_SEC,
    MAX_INPUT_DURATION_SEC,
    MEDIA_STATUS_FAILED,
    MEDIA_STATUS_PARTIAL,
    MEDIA_STATUS_READY,
    MIN_FRAMES_FOR_VISIBILITY_UI,
    MIN_TRANSCRIPT_CHARS,
    SAMPLE_FRAME_COUNT,
)
from invision_api.services.video_processing.face_detection_opencv import frame_has_face
from invision_api.services.video_processing.summary_openai import SummaryGenerationError, summarize_transcript_ru
from invision_api.services.video_processing.transcription_openai import ASRTranscriptionError, transcribe_audio_wav

logger = logging.getLogger(__name__)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_INGESTION_YOUTUBE = "youtube_ytdlp"
_INGESTION_GOOGLE_DRIVE = "google_drive_direct_download"
_INGESTION_DROPBOX = "dropbox_direct_download"
_INGESTION_DIRECT = "direct_ffmpeg"
_INGESTION_NONE = "none"


@dataclass
class VideoPipelineOutcome:
    provider: str
    resource_type: str
    ingestion_strategy: str
    normalized_url: str | None
    access_status: str
    duration_sec: int | None
    duration_formatted: str | None
    width: int | None
    height: int | None
    codec_video: str | None
    codec_audio: str | None
    container: str | None
    has_video_track: bool
    has_audio_track: bool
    sampled_timestamps_sec: list[float]
    frames_extracted_success: int
    face_detected_frames_count: int
    raw_transcript: str
    transcript_source: str
    transcript_confidence: float | None
    captions_language: str | None
    text_acquisition_error_code: str | None
    commission_summary: str
    candidate_visible: bool
    has_speech: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    media_status: str = MEDIA_STATUS_READY


def _format_duration(total_sec: float) -> str:
    sec = int(round(total_sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _failed_outcome(*, errors: list[str], warnings: list[str] | None = None) -> VideoPipelineOutcome:
    w = warnings or []
    return VideoPipelineOutcome(
        provider="unknown",
        resource_type="unknown",
        ingestion_strategy=_INGESTION_NONE,
        normalized_url=None,
        access_status="invalid",
        duration_sec=None,
        duration_formatted=None,
        width=None,
        height=None,
        codec_video=None,
        codec_audio=None,
        container=None,
        has_video_track=False,
        has_audio_track=False,
        sampled_timestamps_sec=[],
        frames_extracted_success=0,
        face_detected_frames_count=0,
        raw_transcript="",
        transcript_source="none",
        transcript_confidence=None,
        captions_language=None,
        text_acquisition_error_code=None,
        commission_summary=COMMISSION_NO_TEXT,
        candidate_visible=False,
        has_speech=False,
        warnings=w,
        errors=errors,
        media_status=MEDIA_STATUS_FAILED,
    )


def _failed_outcome_with_context(
    *,
    errors: list[str],
    warnings: list[str],
    provider: str,
    resource_type: str,
    ingestion_strategy: str,
    normalized_url: str | None,
    access_status: str,
) -> VideoPipelineOutcome:
    out = _failed_outcome(errors=errors, warnings=warnings)
    out.provider = provider or "unknown"
    out.resource_type = resource_type or "unknown"
    out.ingestion_strategy = ingestion_strategy
    out.normalized_url = normalized_url
    out.access_status = access_status
    return out


def _cap_summary_sentences(text: str, *, max_sentences: int = 6) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(s) if p.strip()]
    if not parts or len(parts) <= max_sentences:
        return s
    return " ".join(parts[:max_sentences]).strip()


def _extractive_summary_from_transcript(transcript: str, *, max_sentences: int = 3, max_chars: int = 560) -> str:
    """Fallback summary when LLM summarization is unavailable."""
    raw = (transcript or "").strip()
    if not raw:
        return ""
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(raw) if p.strip()]
    if not parts:
        return ""
    informative = [p for p in parts if len(p) >= 20] or parts
    summary = " ".join(informative[:max_sentences]).strip()
    if len(summary) <= max_chars:
        return summary
    trimmed = summary[:max_chars].rstrip()
    if "." in trimmed:
        trimmed = trimmed.rsplit(".", 1)[0].strip()
    return f"{trimmed}." if trimmed else ""


def _normalized_exception_message(exc: Exception, *, fallback: str) -> str:
    msg = str(exc).strip()
    return msg or fallback


def _ingestion_error_message(exc: Exception) -> str:
    reason = _normalized_exception_message(
        exc,
        fallback="Не удалось загрузить видео по ссылке. Проверьте доступность и формат.",
    )
    return f"Не удалось загрузить видео: {reason}"


def _resolve_ingestion_source(*, provider: str, normalized_url: str) -> tuple[str, str]:
    if provider == "youtube":
        return normalized_url, _INGESTION_YOUTUBE
    if provider == "google_drive":
        direct = ffmpeg_tools.normalize_google_drive_download_url(normalized_url)
        if not direct:
            raise ffmpeg_tools.FFmpegError("Не удалось определить файл Google Drive для загрузки.")
        return direct, _INGESTION_GOOGLE_DRIVE
    if provider == "dropbox":
        direct = ffmpeg_tools.normalize_dropbox_download_url(normalized_url)
        if not direct:
            raise ffmpeg_tools.FFmpegError("Ссылка Dropbox указывает на папку или недоступный ресурс.")
        return direct, _INGESTION_DROPBOX
    return normalized_url, _INGESTION_DIRECT


def run_presentation_pipeline(video_url: str) -> VideoPipelineOutcome:
    """Download/process video locally and produce signals for commission + internal storage."""
    url = (video_url or "").strip()
    if not url.startswith(("http://", "https://")):
        return _failed_outcome(errors=["Некорректный URL видео"])

    preflight = validate_presentation_video_only(url)
    normalized_url = (preflight.normalizedUrl or url).strip()
    provider = preflight.provider
    resource_type = preflight.resourceType
    warnings: list[str] = list(preflight.warnings or [])
    errors: list[str] = []
    access_status = "reachable" if preflight.isAccessible else "unreachable"

    if not preflight.isProcessableVideo:
        reason = (preflight.errors[0] if preflight.errors else None) or "Ссылка не указывает на видеофайл."
        return _failed_outcome_with_context(
            errors=[reason],
            warnings=warnings,
            provider=provider,
            resource_type=resource_type,
            ingestion_strategy=_INGESTION_NONE,
            normalized_url=normalized_url,
            access_status=access_status,
        )
    if not preflight.isValid:
        reason = (preflight.errors[0] if preflight.errors else None) or "Видео по ссылке недоступно для обработки."
        return _failed_outcome_with_context(
            errors=[reason],
            warnings=warnings,
            provider=provider,
            resource_type=resource_type,
            ingestion_strategy=_INGESTION_NONE,
            normalized_url=normalized_url,
            access_status=access_status,
        )

    try:
        ingestion_url, ingestion_strategy = _resolve_ingestion_source(provider=provider, normalized_url=normalized_url)
    except ffmpeg_tools.FFmpegError as exc:
        return _failed_outcome_with_context(
            errors=[str(exc)],
            warnings=warnings,
            provider=provider,
            resource_type=resource_type,
            ingestion_strategy=_INGESTION_NONE,
            normalized_url=normalized_url,
            access_status=access_status,
        )

    tmpdir = tempfile.mkdtemp(prefix="vpipe_")
    local_video: Path | None = None
    try:
        local_video = ffmpeg_tools.make_temp_video_path()
        try:
            try:
                ffmpeg_tools.download_media_url_to_file(ingestion_url, local_video, max_seconds=MAX_INPUT_DURATION_SEC)
            except ffmpeg_tools.FFmpegError as exc:
                logger.warning("ffmpeg download failed: %s", exc)
                return _failed_outcome_with_context(
                    errors=[_ingestion_error_message(exc)],
                    warnings=warnings,
                    provider=provider,
                    resource_type=resource_type,
                    ingestion_strategy=ingestion_strategy,
                    normalized_url=normalized_url,
                    access_status=access_status,
                )

            try:
                metadata = ffmpeg_tools.probe_media_metadata(local_video)
            except ffmpeg_tools.FFmpegError as exc:
                return _failed_outcome_with_context(
                    errors=[f"Не удалось прочитать метаданные видео: {_normalized_exception_message(exc, fallback='ffprobe error')}"],
                    warnings=warnings,
                    provider=provider,
                    resource_type=resource_type,
                    ingestion_strategy=ingestion_strategy,
                    normalized_url=normalized_url,
                    access_status=access_status,
                )
            if not metadata.has_video:
                return _failed_outcome_with_context(
                    errors=["По ссылке не обнаружена видеодорожка."],
                    warnings=warnings,
                    provider=provider,
                    resource_type=resource_type,
                    ingestion_strategy=ingestion_strategy,
                    normalized_url=normalized_url,
                    access_status=access_status,
                )

            duration = metadata.duration_sec
            if duration <= 0:
                return _failed_outcome_with_context(
                    errors=["Не удалось определить длительность видео или файл повреждён."],
                    warnings=warnings,
                    provider=provider,
                    resource_type=resource_type,
                    ingestion_strategy=ingestion_strategy,
                    normalized_url=normalized_url,
                    access_status=access_status,
                )

            dur_int = int(round(duration))
            w, h = metadata.width, metadata.height
            has_v = metadata.has_video
            has_a = metadata.has_audio

            times: list[float] = []
            for i in range(SAMPLE_FRAME_COUNT):
                times.append((i + 0.5) * duration / SAMPLE_FRAME_COUNT)

            face_hits = 0
            frames_ok = 0
            for i, t in enumerate(times):
                png = Path(tmpdir) / f"f{i}.png"
                try:
                    ffmpeg_tools.extract_frame_png(local_video, png, timestamp_sec=t)
                    frames_ok += 1
                    if frame_has_face(png):
                        face_hits += 1
                except ffmpeg_tools.FFmpegError:
                    warnings.append(f"Не удалось извлечь кадр #{i + 1}.")
                except Exception:
                    warnings.append(f"Не удалось проанализировать кадр #{i + 1}.")
                    logger.exception("frame analysis failed frame=%s", i + 1)

            if frames_ok <= 0:
                errors.append("Не удалось извлечь кадры для проверки лица.")
            candidate_visible = frames_ok > 0 and face_hits >= 1

            if 0 < frames_ok < MIN_FRAMES_FOR_VISIBILITY_UI:
                errors.append("Недостаточно кадров для устойчивой проверки лица (частичный сбой извлечения).")

            raw = ""
            transcript_source = "none"
            tr_conf: float | None = None
            asr_failed = False
            captions_language: str | None = None
            text_acquisition_error_code: str | None = None
            captions_infra_error = False
            if has_a:
                wav = Path(tmpdir) / "audio.wav"
                try:
                    audio_cap = min(MAX_AUDIO_FOR_TRANSCRIPTION_SEC, duration)
                    ffmpeg_tools.extract_audio_wav_16k_mono(local_video, wav, max_seconds=audio_cap)
                    try:
                        raw, tr_conf = transcribe_audio_wav(wav)
                        if raw.strip():
                            transcript_source = "asr"
                    except ASRTranscriptionError as exc:
                        asr_failed = True
                        text_acquisition_error_code = "asr_unavailable"
                        warnings.append(
                            f"Транскрибация недоступна: {_normalized_exception_message(exc, fallback='ASR ошибка')}"
                        )
                except ffmpeg_tools.FFmpegError:
                    text_acquisition_error_code = text_acquisition_error_code or "audio_extract_failed"
                    warnings.append("Не удалось извлечь аудио для транскрибации.")
                except Exception:
                    text_acquisition_error_code = text_acquisition_error_code or "audio_extract_failed"
                    warnings.append("Не удалось распознать речь из аудио.")
                    logger.exception("transcription layer raised")
            else:
                text_acquisition_error_code = text_acquisition_error_code or "audio_track_missing"
                warnings.append("Аудиодорожка не обнаружена.")

            has_speech = len(raw.strip()) >= MIN_TRANSCRIPT_CHARS
            if not has_speech and provider == "youtube":
                try:
                    captions = ffmpeg_tools.download_youtube_caption_payload(normalized_url or url)
                    raw = captions.text
                    has_speech = len(raw.strip()) >= MIN_TRANSCRIPT_CHARS
                    if has_speech:
                        transcript_source = "youtube_captions"
                        captions_language = captions.language
                        text_acquisition_error_code = None
                        warnings.append(
                            f"Транскрипт получен из субтитров YouTube ({captions.source}, язык: {captions.language})."
                        )
                except ffmpeg_tools.YouTubeCaptionsError as exc:
                    msg = _normalized_exception_message(exc, fallback="captions error")
                    warnings.append(f"Субтитры YouTube недоступны: {msg}")
                    text_acquisition_error_code = exc.code
                    captions_infra_error = bool(exc.infrastructure)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("youtube captions fallback failed")
                    warnings.append(
                        f"Субтитры YouTube недоступны: {_normalized_exception_message(exc, fallback='captions error')}"
                    )
                    text_acquisition_error_code = "captions_fetch_failed"
                    captions_infra_error = True

            if has_speech:
                try:
                    summary = summarize_transcript_ru(raw).strip()
                except SummaryGenerationError as exc:
                    warnings.append(
                        f"Суммаризация недоступна: {_normalized_exception_message(exc, fallback='LLM summary error')}"
                    )
                    summary = _extractive_summary_from_transcript(raw)
                except Exception as exc:
                    logger.exception("summary layer raised")
                    warnings.append(
                        f"Суммаризация недоступна: {_normalized_exception_message(exc, fallback='LLM summary error')}"
                    )
                    summary = _extractive_summary_from_transcript(raw)
                summary = _cap_summary_sentences(summary, max_sentences=6)
                if not summary:
                    summary = _extractive_summary_from_transcript(raw)
                if not summary:
                    summary = COMMISSION_NO_TEXT
            else:
                summary = COMMISSION_NO_TEXT

            text_infra_issue = False
            if asr_failed and not has_speech:
                text_infra_issue = True
            if captions_infra_error and not has_speech:
                text_infra_issue = True

            if errors:
                media = MEDIA_STATUS_PARTIAL if frames_ok > 0 or has_v else MEDIA_STATUS_FAILED
            elif text_infra_issue:
                media = MEDIA_STATUS_PARTIAL
            else:
                media = MEDIA_STATUS_READY

            return VideoPipelineOutcome(
                provider=provider,
                resource_type=resource_type,
                ingestion_strategy=ingestion_strategy,
                normalized_url=normalized_url,
                access_status=access_status,
                duration_sec=dur_int,
                duration_formatted=_format_duration(duration),
                width=w,
                height=h,
                codec_video=metadata.codec_video,
                codec_audio=metadata.codec_audio,
                container=metadata.container,
                has_video_track=has_v,
                has_audio_track=has_a,
                sampled_timestamps_sec=times,
                frames_extracted_success=frames_ok,
                face_detected_frames_count=face_hits,
                raw_transcript=raw,
                transcript_source=transcript_source,
                transcript_confidence=tr_conf,
                captions_language=captions_language,
                text_acquisition_error_code=text_acquisition_error_code,
                commission_summary=summary,
                candidate_visible=candidate_visible,
                has_speech=has_speech,
                warnings=warnings,
                errors=errors,
                media_status=media,
            )
        except Exception as exc:
            logger.exception("video pipeline crashed")
            return _failed_outcome_with_context(
                errors=[f"Внутренняя ошибка видео-пайплайна: {_normalized_exception_message(exc, fallback='unknown error')}"],
                warnings=warnings,
                provider=provider,
                resource_type=resource_type,
                ingestion_strategy=ingestion_strategy,
                normalized_url=normalized_url,
                access_status=access_status,
            )
    finally:
        try:
            if local_video and local_video.exists():
                local_video.unlink(missing_ok=True)
        except OSError:
            pass
        shutil.rmtree(tmpdir, ignore_errors=True)
