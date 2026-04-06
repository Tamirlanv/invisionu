from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

logger = logging.getLogger(__name__)


class FFmpegError(RuntimeError):
    pass


class YouTubeCaptionsError(FFmpegError):
    def __init__(self, code: str, message: str, *, infrastructure: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.infrastructure = infrastructure


class YouTubeMetadataError(FFmpegError):
    def __init__(self, code: str, message: str, *, infrastructure: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.infrastructure = infrastructure


@dataclass(frozen=True)
class MediaMetadata:
    duration_sec: float
    has_video: bool
    has_audio: bool
    width: int | None
    height: int | None
    codec_video: str | None
    codec_audio: str | None
    container: str | None


@dataclass(frozen=True)
class YouTubeCaptionPayload:
    language: str
    source: str  # manual | auto
    text: str


@dataclass(frozen=True)
class YouTubeMetadataPayload:
    duration_sec: float
    width: int | None
    height: int | None
    has_video: bool
    has_audio: bool
    codec_video: str | None
    codec_audio: str | None
    container: str | None


_TIMECODE_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3}\s+-->\s+\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3}")
_TAG_RE = re.compile(r"<[^>]+>")
_VTT_CUE_SETTINGS_RE = re.compile(r"\b(line|position|size|align|vertical):\S+")
_CAPTION_METADATA_LINE_RE = re.compile(
    r"^(kind|language|x-timestamp-map|region|style)\s*[:=]",
    re.IGNORECASE,
)
_CUE_ID_RE = re.compile(r"^cue-\d+$", re.IGNORECASE)


def _run(args: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    binary = Path(args[0]).name if args else "unknown"
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        missing = Path(exc.filename).name if exc.filename else binary
        raise FFmpegError(
            f"Не найден бинарник '{missing}' в runtime. Установите зависимости ffmpeg/ffprobe/yt-dlp."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(
            f"Команда '{binary}' превысила таймаут {timeout} секунд."
        ) from exc


def resolve_media_runtime_binaries(*, include_ytdlp: bool = True) -> dict[str, str | None]:
    bins: dict[str, str | None] = {
        "ffmpeg": shutil.which("ffmpeg"),
        "ffprobe": shutil.which("ffprobe"),
    }
    if include_ytdlp:
        bins["yt-dlp"] = shutil.which("yt-dlp") or shutil.which("yt_dlp")
    return bins


def ffprobe_json(path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = _run(cmd, timeout=120)
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr or f"ffprobe failed with code {proc.returncode}")
    return json.loads(proc.stdout or "{}")


def probe_duration_sec(path: Path) -> float:
    data = ffprobe_json(path)
    fmt = data.get("format") or {}
    dur = fmt.get("duration")
    if dur is None:
        return 0.0
    try:
        return float(dur)
    except (TypeError, ValueError):
        return 0.0


def probe_media_metadata(path: Path) -> MediaMetadata:
    data = ffprobe_json(path)
    fmt = data.get("format") or {}
    dur_raw = fmt.get("duration")
    duration = 0.0
    try:
        duration = float(dur_raw) if dur_raw is not None else 0.0
    except (TypeError, ValueError):
        duration = 0.0

    width: int | None = None
    height: int | None = None
    codec_video: str | None = None
    codec_audio: str | None = None
    has_video = False
    has_audio = False
    for s in data.get("streams") or []:
        st = s.get("codec_type")
        if st == "video":
            has_video = True
            if codec_video is None and s.get("codec_name"):
                codec_video = str(s.get("codec_name"))
            if width is None or height is None:
                try:
                    width = int(s.get("width")) if s.get("width") is not None else width
                    height = int(s.get("height")) if s.get("height") is not None else height
                except (TypeError, ValueError):
                    width = width if isinstance(width, int) else None
                    height = height if isinstance(height, int) else None
        elif st == "audio":
            has_audio = True
            if codec_audio is None and s.get("codec_name"):
                codec_audio = str(s.get("codec_name"))
    container_raw = fmt.get("format_name")
    container = str(container_raw).split(",")[0].strip() if container_raw else None
    if container == "":
        container = None
    return MediaMetadata(
        duration_sec=duration,
        has_video=has_video,
        has_audio=has_audio,
        width=width,
        height=height,
        codec_video=codec_video,
        codec_audio=codec_audio,
        container=container,
    )


def has_video_stream(path: Path) -> bool:
    data = ffprobe_json(path)
    for s in data.get("streams") or []:
        if s.get("codec_type") == "video":
            return True
    return False


def has_audio_stream(path: Path) -> bool:
    data = ffprobe_json(path)
    for s in data.get("streams") or []:
        if s.get("codec_type") == "audio":
            return True
    return False


def video_dimensions(path: Path) -> tuple[int | None, int | None]:
    data = ffprobe_json(path)
    for s in data.get("streams") or []:
        if s.get("codec_type") == "video":
            w, h = s.get("width"), s.get("height")
            try:
                return (int(w) if w is not None else None, int(h) if h is not None else None)
            except (TypeError, ValueError):
                return None, None
    return None, None


def extract_audio_wav_16k_mono(path: Path, out_wav: Path, *, max_seconds: float | None) -> None:
    args = [
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
    ]
    if max_seconds is not None and max_seconds > 0:
        args.extend(["-t", str(max_seconds)])
    args.append(str(out_wav))
    proc = _run(args, timeout=600)
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr or "ffmpeg audio extract failed")


def extract_frame_png(path: Path, out_png: Path, *, timestamp_sec: float) -> None:
    args = [
        "ffmpeg",
        "-y",
        "-ss",
        str(max(0.0, timestamp_sec)),
        "-i",
        str(path),
        "-vframes",
        "1",
        "-q:v",
        "2",
        str(out_png),
    ]
    proc = _run(args, timeout=120)
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr or "ffmpeg frame extract failed")


def download_or_copy_url_to_file(url: str, out_path: Path, *, max_seconds: int) -> None:
    """Copy media from URL into a local file using ffmpeg (supports many HTTP(S) and streaming sources)."""
    args = [
        "ffmpeg",
        "-y",
        "-i",
        url,
        "-c",
        "copy",
        "-t",
        str(max_seconds),
        str(out_path),
    ]
    proc = _run(args, timeout=3600)
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr or "ffmpeg download failed")


def make_temp_video_path() -> Path:
    fd, name = tempfile.mkstemp(prefix="vp_", suffix=".mkv")
    import os
    os.close(fd)
    return Path(name)

def is_youtube_url(url: str) -> bool:
    u = (url or "").lower()
    return "youtube.com/" in u or "youtu.be/" in u


def is_dropbox_url(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host == "dropbox.com" or host.endswith(".dropbox.com") or host == "db.tt"


def extract_google_drive_file_id(url: str) -> str | None:
    sp = urlsplit(url)
    path = sp.path or ""
    if "/file/d/" in path:
        after = path.split("/file/d/", 1)[1]
        file_id = after.split("/", 1)[0].strip()
        return file_id or None
    query = dict(parse_qsl(sp.query, keep_blank_values=True))
    file_id = (query.get("id") or "").strip()
    return file_id or None


def normalize_google_drive_download_url(url: str) -> str | None:
    file_id = extract_google_drive_file_id(url)
    if not file_id:
        return None
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def normalize_dropbox_download_url(url: str) -> str | None:
    """Convert public Dropbox file/share links into direct-download links.

    Returns ``None`` for obvious folder links.
    """
    sp = urlsplit(url)
    host = (sp.hostname or "").lower()
    if not (host == "dropbox.com" or host.endswith(".dropbox.com") or host == "db.tt"):
        return url
    path = sp.path or ""
    pl = path.lower()
    if "/sh/" in pl or "/scl/fo/" in pl:
        return None
    query = dict(parse_qsl(sp.query, keep_blank_values=True))
    query.pop("raw", None)
    query["dl"] = "1"
    return urlunsplit((sp.scheme or "https", sp.netloc, sp.path, urlencode(query, doseq=True), sp.fragment))


def _select_best_ytdlp_output(files: list[Path]) -> Path:
    """Pick the most useful media artifact produced by yt-dlp.

    Priority:
    1) has video + has audio
    2) has video only
    3) has audio only
    Then larger file size as tie-breaker.
    """
    best: Path | None = None
    best_score = -1
    best_size = -1

    for candidate in files:
        try:
            meta = probe_media_metadata(candidate)
            score = 0
            if meta.has_video:
                score += 2
            if meta.has_audio:
                score += 1
        except FFmpegError:
            score = 0

        try:
            size = int(candidate.stat().st_size)
        except OSError:
            size = 0

        if score > best_score or (score == best_score and size > best_size):
            best = candidate
            best_score = score
            best_size = size

    if best is None or best_score <= 0:
        raise FFmpegError("yt-dlp не смог подготовить пригодный видеофайл с дорожками.")
    return best


def _normalize_caption_text(raw: str) -> str:
    lines = raw.splitlines()
    cleaned: list[str] = []
    seen: set[str] = set()
    for line in lines:
        s = line.strip()
        if not s:
            continue
        su = s.upper()
        if su == "WEBVTT" or su.startswith("NOTE"):
            continue
        if _CAPTION_METADATA_LINE_RE.match(s):
            continue
        if _CUE_ID_RE.match(s):
            continue
        if _TIMECODE_RE.match(s):
            continue
        if s.isdigit():
            continue
        s = _VTT_CUE_SETTINGS_RE.sub("", s).strip()
        s = _TAG_RE.sub("", s).strip()
        s = unescape(s)
        if not s:
            continue
        low = s.lower()
        if low in seen:
            continue
        seen.add(low)
        cleaned.append(s)
    return " ".join(cleaned).strip()


def _caption_priority(lang: str) -> int:
    l = (lang or "").lower()
    if l.startswith("ru"):
        return 0
    if l.startswith("en"):
        return 1
    return 2


def _iter_caption_candidates(meta: dict[str, Any]) -> list[tuple[str, str]]:
    subtitles = meta.get("subtitles") if isinstance(meta.get("subtitles"), dict) else {}
    auto = meta.get("automatic_captions") if isinstance(meta.get("automatic_captions"), dict) else {}

    candidates: list[tuple[int, int, str, str]] = []
    for lang in subtitles.keys():
        candidates.append((_caption_priority(str(lang)), 0, str(lang), "manual"))
    for lang in auto.keys():
        candidates.append((_caption_priority(str(lang)), 1, str(lang), "auto"))
    if not candidates:
        return []
    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    ordered: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for _, _, lang, source in candidates:
        key = (lang, source)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return ordered


def _pick_caption_track(meta: dict[str, Any]) -> tuple[str, str] | None:
    candidates = _iter_caption_candidates(meta)
    return candidates[0] if candidates else None


def fetch_youtube_metadata(url: str, *, timeout_seconds: int = 300) -> YouTubeMetadataPayload:
    ytdlp = resolve_media_runtime_binaries(include_ytdlp=True).get("yt-dlp")
    if not ytdlp:
        raise YouTubeMetadataError(
            "missing_ytdlp",
            "Для обработки YouTube нужен yt-dlp в PATH.",
            infrastructure=True,
        )

    info_args = [
        ytdlp,
        "--no-playlist",
        "--skip-download",
        "--dump-single-json",
        url,
    ]
    info = _run(info_args, timeout=timeout_seconds)
    if info.returncode != 0:
        stderr = (info.stderr or "").strip()
        if "429" in stderr:
            raise YouTubeMetadataError(
                "metadata_rate_limited",
                "YouTube временно ограничил доступ к метаданным (429).",
                infrastructure=True,
            )
        raise YouTubeMetadataError(
            "metadata_fetch_failed",
            stderr or "Не удалось получить метаданные YouTube.",
            infrastructure=True,
        )
    try:
        meta = json.loads(info.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise YouTubeMetadataError(
            "metadata_fetch_failed",
            "Неверный формат метаданных YouTube.",
            infrastructure=True,
        ) from exc

    duration_raw = meta.get("duration")
    try:
        duration = float(duration_raw) if duration_raw is not None else 0.0
    except (TypeError, ValueError):
        duration = 0.0

    width: int | None = None
    height: int | None = None
    for key in ("width", "height"):
        try:
            value = meta.get(key)
            if key == "width":
                width = int(value) if value is not None else None
            else:
                height = int(value) if value is not None else None
        except (TypeError, ValueError):
            if key == "width":
                width = None
            else:
                height = None

    vcodec = str(meta.get("vcodec") or "").strip() or None
    acodec = str(meta.get("acodec") or "").strip() or None
    has_video = bool(vcodec and vcodec.lower() != "none") or bool(width and height)
    has_audio = bool(acodec and acodec.lower() != "none")
    container = str(meta.get("ext") or "").strip() or None

    return YouTubeMetadataPayload(
        duration_sec=duration,
        width=width,
        height=height,
        has_video=has_video,
        has_audio=has_audio,
        codec_video=vcodec if vcodec and vcodec.lower() != "none" else None,
        codec_audio=acodec if acodec and acodec.lower() != "none" else None,
        container=container,
    )


def fetch_youtube_captions_text(url: str, *, timeout_seconds: int = 300) -> YouTubeCaptionPayload:
    ytdlp = resolve_media_runtime_binaries(include_ytdlp=True).get("yt-dlp")
    if not ytdlp:
        raise YouTubeCaptionsError(
            "missing_ytdlp",
            "Для fallback по субтитрам нужен yt-dlp в PATH.",
            infrastructure=True,
        )

    td = tempfile.mkdtemp(prefix="ytcaps_")
    try:
        info_args = [
            ytdlp,
            "--no-playlist",
            "--skip-download",
            "--dump-single-json",
            url,
        ]
        info = _run(info_args, timeout=timeout_seconds)
        if info.returncode != 0:
            stderr = (info.stderr or "").strip()
            if "429" in stderr:
                raise YouTubeCaptionsError(
                    "captions_rate_limited",
                    "YouTube временно ограничил доступ к субтитрам (429).",
                    infrastructure=True,
                )
            raise YouTubeCaptionsError(
                "captions_fetch_failed",
                stderr or "Не удалось получить метаданные субтитров YouTube.",
                infrastructure=True,
            )
        try:
            meta = json.loads(info.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise YouTubeCaptionsError(
                "captions_fetch_failed",
                "Неверный формат метаданных субтитров YouTube.",
                infrastructure=True,
            ) from exc

        candidates = _iter_caption_candidates(meta)
        if not candidates:
            raise YouTubeCaptionsError(
                "captions_unavailable",
                "У видео нет доступных субтитров.",
                infrastructure=False,
            )
        last_infra_error: YouTubeCaptionsError | None = None
        for lang, source in candidates:
            for old in Path(td).glob("src.*"):
                old.unlink(missing_ok=True)

            pattern = str(Path(td) / "src.%(ext)s")
            fetch_args = [
                ytdlp,
                "--no-playlist",
                "--skip-download",
                "--sub-langs",
                lang,
                "--sub-format",
                "vtt",
                "-o",
                pattern,
            ]
            if source == "manual":
                fetch_args.append("--write-sub")
            else:
                fetch_args.append("--write-auto-sub")
            fetch_args.append(url)
            fetched = _run(fetch_args, timeout=timeout_seconds)
            if fetched.returncode != 0:
                stderr = (fetched.stderr or "").strip()
                if "429" in stderr:
                    last_infra_error = YouTubeCaptionsError(
                        "captions_rate_limited",
                        "YouTube временно ограничил доступ к субтитрам (429).",
                        infrastructure=True,
                    )
                else:
                    last_infra_error = YouTubeCaptionsError(
                        "captions_fetch_failed",
                        stderr or "Не удалось скачать субтитры YouTube.",
                        infrastructure=True,
                    )
                continue
            files = [p for p in sorted(Path(td).glob("src.*")) if p.is_file()]
            if not files:
                continue
            raw = ""
            for f in files:
                try:
                    raw = f.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if raw.strip():
                    break
            text = _normalize_caption_text(raw)
            if not text:
                continue
            return YouTubeCaptionPayload(language=lang, source=source, text=text)

        if last_infra_error:
            raise last_infra_error
        raise YouTubeCaptionsError(
            "captions_unavailable",
            "Субтитры не были сохранены yt-dlp.",
            infrastructure=False,
        )
    finally:
        shutil.rmtree(td, ignore_errors=True)


def download_youtube_caption_payload(url: str, *, timeout_seconds: int = 300) -> YouTubeCaptionPayload:
    """Backward-compatible alias."""
    return fetch_youtube_captions_text(url, timeout_seconds=timeout_seconds)


def download_youtube_with_ytdlp(url: str, out_path: Path, *, max_seconds: int) -> None:
    """Download best-effort video via yt-dlp (YouTube is not a direct media URL for ffmpeg -i)."""
    import glob
    import tempfile

    ytdlp = resolve_media_runtime_binaries(include_ytdlp=True).get("yt-dlp")
    if not ytdlp:
        raise FFmpegError(
            "Для ссылок YouTube нужен yt-dlp в PATH. Установите пакет yt-dlp на сервере обработки."
        )
    _ = max_seconds
    td = tempfile.mkdtemp(prefix="ytdl_")
    try:
        pattern = str(Path(td) / "src.%(ext)s")
        args = [
            ytdlp,
            "--no-playlist",
            "-f",
            "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio/best",
            "-o",
            pattern,
            url,
        ]
        proc = _run(args, timeout=3600)
        if proc.returncode != 0:
            raise FFmpegError(proc.stderr or "yt-dlp download failed")
        files = [Path(p) for p in sorted(glob.glob(str(Path(td) / "src.*")))]
        if not files:
            raise FFmpegError("yt-dlp did not produce a video file.")
        src = _select_best_ytdlp_output(files)
        shutil.move(str(src), out_path)
    finally:
        shutil.rmtree(td, ignore_errors=True)
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise FFmpegError("yt-dlp did not produce a video file.")


def download_media_url_to_file(url: str, out_path: Path, *, max_seconds: int) -> None:
    """HTTP(S) direct media via ffmpeg; YouTube via yt-dlp when available."""
    if is_youtube_url(url):
        download_youtube_with_ytdlp(url, out_path, max_seconds=max_seconds)
    else:
        download_or_copy_url_to_file(url, out_path, max_seconds=max_seconds)
