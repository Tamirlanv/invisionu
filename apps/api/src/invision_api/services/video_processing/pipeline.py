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
    COMMISSION_VIDEO_TOO_LONG,
    MAX_AUDIO_FOR_TRANSCRIPTION_SEC,
    MAX_INPUT_DURATION_SEC,
    MAX_YOUTUBE_SUMMARY_DURATION_SEC,
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
_MULTISPACE_RE = re.compile(r"\s+")
_TRANSCRIPT_TECH_LINE_RE = re.compile(
    r"^\s*(kind|language|x-timestamp-map|region|style)\s*[:=]",
    re.IGNORECASE,
)
_TRANSCRIPT_TECH_SENTENCE_RE = re.compile(
    r"(?:^|\s)(webvtt|kind\s*[:=]|language\s*[:=]|x-timestamp-map\s*[:=]|region\s*[:=]|style\s*[:=])|-->",
    re.IGNORECASE,
)

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


def _failed_outcome(
    *,
    errors: list[str],
    warnings: list[str] | None = None,
    text_acquisition_error_code: str | None = None,
) -> VideoPipelineOutcome:
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
        text_acquisition_error_code=text_acquisition_error_code,
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
    text_acquisition_error_code: str | None = None,
) -> VideoPipelineOutcome:
    out = _failed_outcome(
        errors=errors,
        warnings=warnings,
        text_acquisition_error_code=text_acquisition_error_code,
    )
    out.provider = provider or "unknown"
    out.resource_type = resource_type or "unknown"
    out.ingestion_strategy = ingestion_strategy
    out.normalized_url = normalized_url
    out.access_status = access_status
    return out


def _normalize_summary_sentences(text: str, *, min_sentences: int = 7, max_sentences: int = 8) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(s) if p.strip()]
    if len(parts) < min_sentences:
        return ""
    if len(parts) > max_sentences:
        parts = parts[:max_sentences]
    return " ".join(parts).strip()


def _clean_transcript_for_summary(raw_text: str) -> str:
    cleaned_lines: list[str] = []
    for line in str(raw_text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.upper() == "WEBVTT" or line.upper().startswith("NOTE"):
            continue
        if _TRANSCRIPT_TECH_LINE_RE.match(line):
            continue
        if re.match(r"^\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3}\s+-->\s+\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3}", line):
            continue
        if line.isdigit():
            continue
        cleaned_lines.append(line)

    cleaned = _MULTISPACE_RE.sub(" ", " ".join(cleaned_lines)).strip()
    if not cleaned:
        return ""

    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(cleaned) if p.strip()]
    filtered = [p for p in parts if not _TRANSCRIPT_TECH_SENTENCE_RE.search(p)]
    if filtered:
        cleaned = " ".join(filtered).strip()
    return _MULTISPACE_RE.sub(" ", cleaned).strip()


def _sanitize_summary_text(text: str) -> str:
    summary = _MULTISPACE_RE.sub(" ", str(text or "")).strip()
    if not summary:
        return ""
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(summary) if p.strip()]
    filtered = [p for p in parts if not _TRANSCRIPT_TECH_SENTENCE_RE.search(p)]
    if not filtered:
        return ""
    return " ".join(filtered).strip()


def _norm_for_compare(text: str) -> str:
    return re.sub(r"[\W_]+", "", _MULTISPACE_RE.sub(" ", text).lower(), flags=re.UNICODE)


def _looks_like_transcript_dump(summary: str, transcript: str) -> bool:
    s = _MULTISPACE_RE.sub(" ", str(summary or "")).strip()
    t = _MULTISPACE_RE.sub(" ", str(transcript or "")).strip()
    if not s or not t:
        return False
    if len(t) < 500:
        return False
    if len(s) >= int(len(t) * 0.85):
        return True

    s_parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(s) if p.strip()]
    t_parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(t) if p.strip()]
    if len(s_parts) < 5 or not t_parts:
        return False
    t_norm = {_norm_for_compare(p) for p in t_parts if p.strip()}
    matched = sum(1 for p in s_parts if _norm_for_compare(p) in t_norm)
    return (matched / len(s_parts)) >= 0.85 and len(s) >= 250


def _sentence_priority(sentence: str) -> int:
    s = sentence.lower()
    score = 0
    markers = (
        "сделал",
        "сделала",
        "создал",
        "создала",
        "запустил",
        "запустила",
        "организовал",
        "организовала",
        "проект",
        "результат",
        "достиг",
        "достигла",
        "опыт",
        "цель",
        "вывод",
        "понял",
        "поняла",
        "научил",
        "научилась",
    )
    for marker in markers:
        if marker in s:
            score += 1
    if re.search(r"\d", s):
        score += 1
    return score


def _pick_evenly_distributed(items: list[str], *, count: int) -> list[str]:
    if not items or count <= 0:
        return []
    if len(items) <= count:
        return items[:]

    picked_indices: list[int] = []
    used: set[int] = set()
    for i in range(count):
        idx = round(i * (len(items) - 1) / max(1, count - 1))
        if idx in used:
            shift = idx + 1
            while shift < len(items) and shift in used:
                shift += 1
            if shift < len(items):
                idx = shift
            else:
                shift = idx - 1
                while shift >= 0 and shift in used:
                    shift -= 1
                if shift >= 0:
                    idx = shift
        used.add(idx)
        picked_indices.append(idx)
    picked_indices.sort()
    return [items[i] for i in picked_indices]


def _extractive_summary_from_transcript(
    transcript: str,
    *,
    min_sentences: int = 7,
    max_sentences: int = 8,
    max_chars: int = 1800,
) -> str:
    """Whole-transcript fallback summary for LLM failures."""
    raw = (transcript or "").strip()
    if not raw:
        return ""
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(raw) if p.strip()]
    informative = [p for p in parts if len(p) >= 20]
    if len(informative) < min_sentences:
        return ""
    factual = [p for p in informative if _sentence_priority(p) > 0]
    source = factual if len(factual) >= min_sentences else informative
    selected = _pick_evenly_distributed(source, count=max_sentences)
    if len(selected) < min_sentences:
        return ""

    while selected and len(" ".join(selected)) > max_chars:
        selected.pop()
    if len(selected) < min_sentences:
        return ""
    return " ".join(selected).strip()


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


def _build_commission_summary(cleaned_transcript: str, warnings: list[str]) -> str:
    if len(cleaned_transcript) < MIN_TRANSCRIPT_CHARS:
        return COMMISSION_NO_TEXT
    try:
        summary = summarize_transcript_ru(cleaned_transcript).strip()
    except SummaryGenerationError as exc:
        warnings.append(
            f"Суммаризация недоступна: {_normalized_exception_message(exc, fallback='LLM summary error')}"
        )
        summary = _extractive_summary_from_transcript(cleaned_transcript, min_sentences=7, max_sentences=8)
    except Exception as exc:  # noqa: BLE001
        logger.exception("summary layer raised")
        warnings.append(
            f"Суммаризация недоступна: {_normalized_exception_message(exc, fallback='LLM summary error')}"
        )
        summary = _extractive_summary_from_transcript(cleaned_transcript, min_sentences=7, max_sentences=8)

    summary = _sanitize_summary_text(summary)
    summary = _normalize_summary_sentences(summary, min_sentences=7, max_sentences=8)
    if summary and _looks_like_transcript_dump(summary, cleaned_transcript):
        warnings.append("Суммаризация вернула сырой фрагмент; применена извлекающая выжимка.")
        summary = ""
    if not summary:
        summary = _extractive_summary_from_transcript(cleaned_transcript, min_sentences=7, max_sentences=8)
        summary = _sanitize_summary_text(summary)
        summary = _normalize_summary_sentences(summary, min_sentences=7, max_sentences=8)
    if not summary:
        summary = COMMISSION_NO_TEXT
    return summary


def _run_youtube_subtitles_pipeline(
    *,
    source_url: str,
    provider: str,
    resource_type: str,
    normalized_url: str,
    access_status: str,
    warnings: list[str],
) -> VideoPipelineOutcome:
    try:
        metadata = ffmpeg_tools.fetch_youtube_metadata(normalized_url or source_url)
    except ffmpeg_tools.YouTubeMetadataError as exc:
        msg = _normalized_exception_message(exc, fallback="Не удалось получить метаданные YouTube.")
        return _failed_outcome_with_context(
            errors=[msg],
            warnings=warnings,
            provider=provider,
            resource_type=resource_type,
            ingestion_strategy=_INGESTION_YOUTUBE,
            normalized_url=normalized_url,
            access_status=access_status,
            text_acquisition_error_code=exc.code,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("youtube metadata fetch failed")
        msg = _normalized_exception_message(exc, fallback="Не удалось получить метаданные YouTube.")
        return _failed_outcome_with_context(
            errors=[msg],
            warnings=warnings,
            provider=provider,
            resource_type=resource_type,
            ingestion_strategy=_INGESTION_YOUTUBE,
            normalized_url=normalized_url,
            access_status=access_status,
            text_acquisition_error_code="metadata_fetch_failed",
        )

    duration = float(metadata.duration_sec or 0.0)
    if not metadata.has_video:
        return _failed_outcome_with_context(
            errors=["По ссылке не обнаружена видеодорожка."],
            warnings=warnings,
            provider=provider,
            resource_type=resource_type,
            ingestion_strategy=_INGESTION_YOUTUBE,
            normalized_url=normalized_url,
            access_status=access_status,
            text_acquisition_error_code="metadata_video_track_missing",
        )
    if duration <= 0:
        return _failed_outcome_with_context(
            errors=["Не удалось определить длительность YouTube видео."],
            warnings=warnings,
            provider=provider,
            resource_type=resource_type,
            ingestion_strategy=_INGESTION_YOUTUBE,
            normalized_url=normalized_url,
            access_status=access_status,
            text_acquisition_error_code="metadata_duration_missing",
        )

    dur_int = int(round(duration))
    if dur_int > MAX_YOUTUBE_SUMMARY_DURATION_SEC:
        return VideoPipelineOutcome(
            provider=provider,
            resource_type=resource_type,
            ingestion_strategy=_INGESTION_YOUTUBE,
            normalized_url=normalized_url,
            access_status=access_status,
            duration_sec=dur_int,
            duration_formatted=_format_duration(duration),
            width=metadata.width,
            height=metadata.height,
            codec_video=metadata.codec_video,
            codec_audio=metadata.codec_audio,
            container=metadata.container,
            has_video_track=metadata.has_video,
            has_audio_track=metadata.has_audio,
            sampled_timestamps_sec=[],
            frames_extracted_success=0,
            face_detected_frames_count=0,
            raw_transcript="",
            transcript_source="none",
            transcript_confidence=None,
            captions_language=None,
            text_acquisition_error_code=None,
            commission_summary=COMMISSION_VIDEO_TOO_LONG,
            candidate_visible=False,
            has_speech=False,
            warnings=warnings,
            errors=[],
            media_status=MEDIA_STATUS_READY,
        )

    try:
        captions = ffmpeg_tools.fetch_youtube_captions_text(normalized_url or source_url)
    except ffmpeg_tools.YouTubeCaptionsError as exc:
        msg = _normalized_exception_message(exc, fallback="Субтитры YouTube недоступны.")
        return VideoPipelineOutcome(
            provider=provider,
            resource_type=resource_type,
            ingestion_strategy=_INGESTION_YOUTUBE,
            normalized_url=normalized_url,
            access_status=access_status,
            duration_sec=dur_int,
            duration_formatted=_format_duration(duration),
            width=metadata.width,
            height=metadata.height,
            codec_video=metadata.codec_video,
            codec_audio=metadata.codec_audio,
            container=metadata.container,
            has_video_track=metadata.has_video,
            has_audio_track=metadata.has_audio,
            sampled_timestamps_sec=[],
            frames_extracted_success=0,
            face_detected_frames_count=0,
            raw_transcript="",
            transcript_source="none",
            transcript_confidence=None,
            captions_language=None,
            text_acquisition_error_code=exc.code,
            commission_summary=COMMISSION_NO_TEXT,
            candidate_visible=False,
            has_speech=False,
            warnings=[*warnings, f"Субтитры YouTube недоступны: {msg}"],
            errors=[],
            media_status=MEDIA_STATUS_PARTIAL,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("youtube captions fetch failed")
        msg = _normalized_exception_message(exc, fallback="Субтитры YouTube недоступны.")
        return VideoPipelineOutcome(
            provider=provider,
            resource_type=resource_type,
            ingestion_strategy=_INGESTION_YOUTUBE,
            normalized_url=normalized_url,
            access_status=access_status,
            duration_sec=dur_int,
            duration_formatted=_format_duration(duration),
            width=metadata.width,
            height=metadata.height,
            codec_video=metadata.codec_video,
            codec_audio=metadata.codec_audio,
            container=metadata.container,
            has_video_track=metadata.has_video,
            has_audio_track=metadata.has_audio,
            sampled_timestamps_sec=[],
            frames_extracted_success=0,
            face_detected_frames_count=0,
            raw_transcript="",
            transcript_source="none",
            transcript_confidence=None,
            captions_language=None,
            text_acquisition_error_code="captions_fetch_failed",
            commission_summary=COMMISSION_NO_TEXT,
            candidate_visible=False,
            has_speech=False,
            warnings=[*warnings, f"Субтитры YouTube недоступны: {msg}"],
            errors=[],
            media_status=MEDIA_STATUS_PARTIAL,
        )

    cleaned_transcript = _clean_transcript_for_summary(captions.text)
    if len(cleaned_transcript) < MIN_TRANSCRIPT_CHARS:
        return VideoPipelineOutcome(
            provider=provider,
            resource_type=resource_type,
            ingestion_strategy=_INGESTION_YOUTUBE,
            normalized_url=normalized_url,
            access_status=access_status,
            duration_sec=dur_int,
            duration_formatted=_format_duration(duration),
            width=metadata.width,
            height=metadata.height,
            codec_video=metadata.codec_video,
            codec_audio=metadata.codec_audio,
            container=metadata.container,
            has_video_track=metadata.has_video,
            has_audio_track=metadata.has_audio,
            sampled_timestamps_sec=[],
            frames_extracted_success=0,
            face_detected_frames_count=0,
            raw_transcript=cleaned_transcript,
            transcript_source="youtube_captions",
            transcript_confidence=None,
            captions_language=captions.language,
            text_acquisition_error_code="captions_text_too_short",
            commission_summary=COMMISSION_NO_TEXT,
            candidate_visible=False,
            has_speech=False,
            warnings=[*warnings, "Субтитры доступны, но текста недостаточно для сводки."],
            errors=[],
            media_status=MEDIA_STATUS_PARTIAL,
        )

    summary_warnings = list(warnings)
    summary = _build_commission_summary(cleaned_transcript, summary_warnings)
    return VideoPipelineOutcome(
        provider=provider,
        resource_type=resource_type,
        ingestion_strategy=_INGESTION_YOUTUBE,
        normalized_url=normalized_url,
        access_status=access_status,
        duration_sec=dur_int,
        duration_formatted=_format_duration(duration),
        width=metadata.width,
        height=metadata.height,
        codec_video=metadata.codec_video,
        codec_audio=metadata.codec_audio,
        container=metadata.container,
        has_video_track=metadata.has_video,
        has_audio_track=metadata.has_audio,
        sampled_timestamps_sec=[],
        frames_extracted_success=0,
        face_detected_frames_count=0,
        raw_transcript=cleaned_transcript,
        transcript_source="youtube_captions",
        transcript_confidence=None,
        captions_language=captions.language,
        text_acquisition_error_code=None,
        commission_summary=summary,
        candidate_visible=False,
        has_speech=True,
        warnings=summary_warnings,
        errors=[],
        media_status=MEDIA_STATUS_READY,
    )


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

    if provider == "youtube":
        return _run_youtube_subtitles_pipeline(
            source_url=url,
            provider=provider,
            resource_type=resource_type,
            normalized_url=normalized_url,
            access_status=access_status,
            warnings=warnings,
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

            cleaned_transcript = _clean_transcript_for_summary(raw)
            has_speech = len(cleaned_transcript) >= MIN_TRANSCRIPT_CHARS
            summary = _build_commission_summary(cleaned_transcript, warnings) if has_speech else COMMISSION_NO_TEXT

            text_infra_issue = False
            if asr_failed and not has_speech:
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
                raw_transcript=cleaned_transcript,
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
