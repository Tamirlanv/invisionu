"""Review-hardened tests: video pipeline outcomes and commission mapper (no ffmpeg)."""

from __future__ import annotations

import re
import subprocess
from types import SimpleNamespace

from invision_api.commission.application.personal_info_mapper import _map_video_presentation_commission
from invision_api.services.link_validation.types import VideoLinkValidationResult
from invision_api.services.video_processing import ffmpeg_tools
from invision_api.services.video_processing.ffmpeg_tools import FFmpegError, MediaMetadata, YouTubeCaptionsError
from invision_api.services.video_processing.pipeline import run_presentation_pipeline
from invision_api.services.video_processing.summary_openai import SummaryProviderError
from invision_api.services.video_processing.transcription_openai import ASRProviderError


def test_invalid_url_is_failed_status() -> None:
    o = run_presentation_pipeline("not-a-url")
    assert o.media_status == "failed"
    assert o.errors
    assert o.frames_extracted_success == 0


def test_map_commission_failed_only_url() -> None:
    row = SimpleNamespace(
        media_status="failed",
        duration_sec=120,
        total_frames_analyzed=6,
        likely_face_visible=True,
        summary_text="x",
    )
    v = _map_video_presentation_commission("https://example.com/v.mp4", row)
    assert v == {"url": "https://example.com/v.mp4", "borderTone": "gray"}


def test_map_commission_visibility_requires_min_frames() -> None:
    row = SimpleNamespace(
        media_status="ready",
        duration_sec=120,
        total_frames_analyzed=3,
        likely_face_visible=True,
        summary_text="Краткое содержание.",
    )
    v = _map_video_presentation_commission("https://example.com/v.mp4", row)
    assert v is not None
    assert v.get("duration") == "2:00"
    assert v.get("candidateVisibility") is None
    assert v.get("summary")


def test_map_commission_ready_full_visibility() -> None:
    row = SimpleNamespace(
        media_status="ready",
        duration_sec=125,
        total_frames_analyzed=6,
        likely_face_visible=False,
        summary_text="Текст не обнаружен",
    )
    v = _map_video_presentation_commission("https://example.com/v.mp4", row)
    assert v.get("candidateVisibility") == "кандидата не видно"


def _ok_preflight(provider: str = "direct") -> VideoLinkValidationResult:
    return VideoLinkValidationResult(
        isValid=True,
        provider=provider,  # type: ignore[arg-type]
        resourceType="video",
        isAccessible=True,
        isProcessableVideo=True,
        detectedMimeType="video/mp4",
        detectedExtension=".mp4",
        normalizedUrl="https://cdn.example.com/video.mp4",
        errors=[],
        warnings=[],
    )


def test_pipeline_visibility_true_when_face_found_on_single_frame(monkeypatch, tmp_path) -> None:
    out_path = tmp_path / "video.mkv"
    out_path.write_bytes(b"ok")

    monkeypatch.setattr("invision_api.services.video_processing.pipeline.validate_presentation_video_only", lambda _url: _ok_preflight())
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.make_temp_video_path", lambda: out_path)
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.download_media_url_to_file",
        lambda _url, _out, max_seconds: None,
    )
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.probe_media_metadata",
        lambda _path: MediaMetadata(
            duration_sec=120.0,
            has_video=True,
            has_audio=True,
            width=1280,
            height=720,
            codec_video="h264",
            codec_audio="aac",
            container="mov,mp4,m4a,3gp,3g2,mj2",
        ),
    )
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.extract_frame_png", lambda _p, png, timestamp_sec: png.write_bytes(b"x"))
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.extract_audio_wav_16k_mono", lambda _p, wav, max_seconds: wav.write_bytes(b"wav"))

    calls = {"idx": 0}

    def _face(_png) -> bool:
        calls["idx"] += 1
        return calls["idx"] == 1

    monkeypatch.setattr("invision_api.services.video_processing.pipeline.frame_has_face", _face)
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.transcribe_audio_wav", lambda _wav: ("Текст " * 100, None))
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.summarize_transcript_ru",
        lambda _raw: "Раз. Два. Три. Четыре. Пять. Шесть. Семь. Восемь.",
    )

    out = run_presentation_pipeline("https://cdn.example.com/video.mp4")
    assert out.media_status == "ready"
    assert out.duration_sec == 120
    assert out.codec_video == "h264"
    assert out.codec_audio == "aac"
    assert out.container == "mov,mp4,m4a,3gp,3g2,mj2"
    assert out.candidate_visible is True
    # Summary should be capped to <= 6 sentences.
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", out.commission_summary.strip()) if s]
    assert len(sentences) <= 6


def test_pipeline_no_transcript_returns_no_text(monkeypatch, tmp_path) -> None:
    out_path = tmp_path / "video2.mkv"
    out_path.write_bytes(b"ok")

    monkeypatch.setattr("invision_api.services.video_processing.pipeline.validate_presentation_video_only", lambda _url: _ok_preflight())
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.make_temp_video_path", lambda: out_path)
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.download_media_url_to_file",
        lambda _url, _out, max_seconds: None,
    )
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.probe_media_metadata",
        lambda _path: MediaMetadata(
            duration_sec=75.0,
            has_video=True,
            has_audio=True,
            width=1920,
            height=1080,
            codec_video="h265",
            codec_audio="aac",
            container="matroska",
        ),
    )
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.extract_frame_png", lambda _p, png, timestamp_sec: png.write_bytes(b"x"))
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.frame_has_face", lambda _png: False)
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.extract_audio_wav_16k_mono", lambda _p, wav, max_seconds: wav.write_bytes(b"wav"))
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.transcribe_audio_wav", lambda _wav: ("коротко", None))

    out = run_presentation_pipeline("https://cdn.example.com/video2.mp4")
    assert out.media_status == "ready"
    assert out.commission_summary == "Текст не обнаружен"


def test_pipeline_returns_failed_when_download_dependency_missing(monkeypatch, tmp_path) -> None:
    out_path = tmp_path / "video3.mkv"
    out_path.write_bytes(b"ok")

    monkeypatch.setattr("invision_api.services.video_processing.pipeline.validate_presentation_video_only", lambda _url: _ok_preflight())
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.make_temp_video_path", lambda: out_path)
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.download_media_url_to_file",
        lambda _url, _out, max_seconds: (_ for _ in ()).throw(
            FFmpegError("Не найден бинарник 'ffmpeg' в runtime. Установите зависимости ffmpeg/ffprobe/yt-dlp.")
        ),
    )

    out = run_presentation_pipeline("https://cdn.example.com/video3.mp4")
    assert out.media_status == "failed"
    assert out.errors
    assert any("ffmpeg" in e.lower() for e in out.errors)


def test_pipeline_returns_failed_with_explicit_ytdlp_reason(monkeypatch, tmp_path) -> None:
    out_path = tmp_path / "video4.mkv"
    out_path.write_bytes(b"ok")

    monkeypatch.setattr("invision_api.services.video_processing.pipeline.validate_presentation_video_only", lambda _url: _ok_preflight("youtube"))
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.make_temp_video_path", lambda: out_path)
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.download_media_url_to_file",
        lambda _url, _out, max_seconds: (_ for _ in ()).throw(
            FFmpegError("Для ссылок YouTube нужен yt-dlp в PATH. Установите пакет yt-dlp на сервере обработки.")
        ),
    )

    out = run_presentation_pipeline("https://youtube.com/watch?v=abc")
    assert out.media_status == "failed"
    assert out.errors
    assert any("yt-dlp" in e.lower() for e in out.errors)


def test_pipeline_returns_failed_when_probe_fails(monkeypatch, tmp_path) -> None:
    out_path = tmp_path / "video5.mkv"
    out_path.write_bytes(b"ok")

    monkeypatch.setattr("invision_api.services.video_processing.pipeline.validate_presentation_video_only", lambda _url: _ok_preflight())
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.make_temp_video_path", lambda: out_path)
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.download_media_url_to_file",
        lambda _url, _out, max_seconds: None,
    )
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.probe_media_metadata",
        lambda _path: (_ for _ in ()).throw(
            FFmpegError("Не найден бинарник 'ffprobe' в runtime. Установите зависимости ffmpeg/ffprobe/yt-dlp.")
        ),
    )

    out = run_presentation_pipeline("https://cdn.example.com/video5.mp4")
    assert out.media_status == "failed"
    assert any("ffprobe" in e.lower() for e in out.errors)


def test_ffmpeg_tools_run_maps_missing_binary_to_ffmpeg_error(monkeypatch) -> None:
    def _raise(*_a, **_k):
        raise FileNotFoundError(2, "No such file or directory", "ffmpeg")

    monkeypatch.setattr(subprocess, "run", _raise)
    try:
        ffmpeg_tools._run(["ffmpeg", "-version"])
    except FFmpegError as exc:
        assert "ffmpeg" in str(exc).lower()
    else:
        raise AssertionError("Expected FFmpegError")


def test_ffmpeg_tools_run_maps_timeout_to_ffmpeg_error(monkeypatch) -> None:
    def _raise(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="ffprobe", timeout=5)

    monkeypatch.setattr(subprocess, "run", _raise)
    try:
        ffmpeg_tools._run(["ffprobe", "-version"], timeout=5)
    except FFmpegError as exc:
        assert "таймаут" in str(exc).lower()
    else:
        raise AssertionError("Expected FFmpegError")


def test_pipeline_asr_failure_is_partial_manual_path(monkeypatch, tmp_path) -> None:
    out_path = tmp_path / "video6.mkv"
    out_path.write_bytes(b"ok")

    monkeypatch.setattr("invision_api.services.video_processing.pipeline.validate_presentation_video_only", lambda _url: _ok_preflight())
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.make_temp_video_path", lambda: out_path)
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.download_media_url_to_file",
        lambda _url, _out, max_seconds: None,
    )
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.probe_media_metadata",
        lambda _path: MediaMetadata(
            duration_sec=75.0,
            has_video=True,
            has_audio=True,
            width=1280,
            height=720,
            codec_video="h264",
            codec_audio="aac",
            container="mp4",
        ),
    )
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.extract_frame_png", lambda _p, png, timestamp_sec: png.write_bytes(b"x"))
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.frame_has_face", lambda _png: False)
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.extract_audio_wav_16k_mono", lambda _p, wav, max_seconds: wav.write_bytes(b"wav"))
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.transcribe_audio_wav",
        lambda _wav: (_ for _ in ()).throw(ASRProviderError("upstream 503")),
    )

    out = run_presentation_pipeline("https://cdn.example.com/video6.mp4")
    assert out.media_status == "partial"
    assert out.commission_summary == "Текст не обнаружен"
    assert any("транскрибация недоступна" in w.lower() for w in out.warnings)


def test_pipeline_summary_provider_failure_uses_extractive_fallback(monkeypatch, tmp_path) -> None:
    out_path = tmp_path / "video7.mkv"
    out_path.write_bytes(b"ok")

    monkeypatch.setattr("invision_api.services.video_processing.pipeline.validate_presentation_video_only", lambda _url: _ok_preflight())
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.make_temp_video_path", lambda: out_path)
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.download_media_url_to_file",
        lambda _url, _out, max_seconds: None,
    )
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.probe_media_metadata",
        lambda _path: MediaMetadata(
            duration_sec=120.0,
            has_video=True,
            has_audio=True,
            width=1280,
            height=720,
            codec_video="h264",
            codec_audio="aac",
            container="mp4",
        ),
    )
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.extract_frame_png", lambda _p, png, timestamp_sec: png.write_bytes(b"x"))
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.frame_has_face", lambda _png: True)
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.extract_audio_wav_16k_mono", lambda _p, wav, max_seconds: wav.write_bytes(b"wav"))
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.transcribe_audio_wav",
        lambda _wav: (
            "Я начал делать проект сам. Потом собрал команду и распределил роли. "
            "Мы столкнулись с проблемами и я довёл задачу до конца. "
            "Я понял, как лучше планировать работу и учиться на ошибках.",
            None,
        ),
    )
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.summarize_transcript_ru",
        lambda _raw: (_ for _ in ()).throw(SummaryProviderError("provider down")),
    )

    out = run_presentation_pipeline("https://cdn.example.com/video7.mp4")
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", out.commission_summary.strip()) if s]
    assert out.media_status == "ready"
    assert out.commission_summary != "Текст не обнаружен"
    assert 1 <= len(sentences) <= 3
    assert any("суммаризация недоступна" in w.lower() for w in out.warnings)


def test_pipeline_youtube_captions_fallback_on_asr_failure(monkeypatch, tmp_path) -> None:
    out_path = tmp_path / "video8.mkv"
    out_path.write_bytes(b"ok")

    monkeypatch.setattr("invision_api.services.video_processing.pipeline.validate_presentation_video_only", lambda _url: _ok_preflight("youtube"))
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.make_temp_video_path", lambda: out_path)
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.download_media_url_to_file",
        lambda _url, _out, max_seconds: None,
    )
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.probe_media_metadata",
        lambda _path: MediaMetadata(
            duration_sec=180.0,
            has_video=True,
            has_audio=True,
            width=1280,
            height=720,
            codec_video="h264",
            codec_audio="aac",
            container="mp4",
        ),
    )
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.extract_frame_png", lambda _p, png, timestamp_sec: png.write_bytes(b"x"))
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.frame_has_face", lambda _png: True)
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.extract_audio_wav_16k_mono", lambda _p, wav, max_seconds: wav.write_bytes(b"wav"))
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.transcribe_audio_wav",
        lambda _wav: (_ for _ in ()).throw(ASRProviderError("asr down")),
    )
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.download_youtube_caption_payload",
        lambda _url: ffmpeg_tools.YouTubeCaptionPayload(
            language="en",
            source="auto",
            text="Кандидат рассказывает о проекте и своём опыте в команде. Он описывает результат и выводы.",
        ),
    )

    out = run_presentation_pipeline("https://youtube.com/watch?v=abc")
    assert out.media_status == "ready"
    assert out.transcript_source == "youtube_captions"
    assert out.captions_language == "en"
    assert out.text_acquisition_error_code is None
    assert out.commission_summary != "Текст не обнаружен"


def test_pipeline_youtube_captions_infra_failure_keeps_partial(monkeypatch, tmp_path) -> None:
    out_path = tmp_path / "video9.mkv"
    out_path.write_bytes(b"ok")

    monkeypatch.setattr("invision_api.services.video_processing.pipeline.validate_presentation_video_only", lambda _url: _ok_preflight("youtube"))
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.make_temp_video_path", lambda: out_path)
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.download_media_url_to_file",
        lambda _url, _out, max_seconds: None,
    )
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.probe_media_metadata",
        lambda _path: MediaMetadata(
            duration_sec=180.0,
            has_video=True,
            has_audio=True,
            width=1280,
            height=720,
            codec_video="h264",
            codec_audio="aac",
            container="mp4",
        ),
    )
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.extract_frame_png", lambda _p, png, timestamp_sec: png.write_bytes(b"x"))
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.frame_has_face", lambda _png: True)
    monkeypatch.setattr("invision_api.services.video_processing.pipeline.ffmpeg_tools.extract_audio_wav_16k_mono", lambda _p, wav, max_seconds: wav.write_bytes(b"wav"))
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.transcribe_audio_wav",
        lambda _wav: (_ for _ in ()).throw(ASRProviderError("asr timeout")),
    )
    monkeypatch.setattr(
        "invision_api.services.video_processing.pipeline.ffmpeg_tools.download_youtube_caption_payload",
        lambda _url: (_ for _ in ()).throw(
            YouTubeCaptionsError("captions_rate_limited", "429", infrastructure=True)
        ),
    )

    out = run_presentation_pipeline("https://youtube.com/watch?v=abc")
    assert out.media_status == "partial"
    assert out.transcript_source == "none"
    assert out.text_acquisition_error_code == "captions_rate_limited"
    assert out.commission_summary == "Текст не обнаружен"


def test_select_best_ytdlp_output_prefers_video_with_audio(monkeypatch, tmp_path) -> None:
    v_only = tmp_path / "src.v.mp4"
    av = tmp_path / "src.av.mp4"
    a_only = tmp_path / "src.a.m4a"
    v_only.write_bytes(b"x" * 10)
    av.write_bytes(b"x" * 20)
    a_only.write_bytes(b"x" * 30)

    mapping = {
        v_only: MediaMetadata(1.0, True, False, 100, 100, "h264", None, "mp4"),
        av: MediaMetadata(1.0, True, True, 100, 100, "h264", "aac", "mp4"),
        a_only: MediaMetadata(1.0, False, True, None, None, None, "aac", "m4a"),
    }

    monkeypatch.setattr(
        "invision_api.services.video_processing.ffmpeg_tools.probe_media_metadata",
        lambda path: mapping[path],
    )
    selected = ffmpeg_tools._select_best_ytdlp_output([v_only, av, a_only])
    assert selected == av


def test_pick_caption_track_prefers_ru_then_en_then_any() -> None:
    meta = {
        "subtitles": {"fr": [{}]},
        "automatic_captions": {"en": [{}], "ru": [{}]},
    }
    lang, source = ffmpeg_tools._pick_caption_track(meta)  # type: ignore[attr-defined]
    assert lang == "ru"
    assert source == "auto"


def test_normalize_caption_text_removes_timecodes_and_tags() -> None:
    raw = """WEBVTT

00:00:00.000 --> 00:00:01.200 align:start
<c>Привет</c>

00:00:01.300 --> 00:00:02.500
Привет
Мир
"""
    txt = ffmpeg_tools._normalize_caption_text(raw)  # type: ignore[attr-defined]
    assert "WEBVTT" not in txt
    assert "-->" not in txt
    assert "<c>" not in txt
    assert txt == "Привет Мир"
