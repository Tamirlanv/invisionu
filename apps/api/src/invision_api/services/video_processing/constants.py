"""Constants for candidate video presentation processing."""

SAMPLE_FRAME_COUNT = 6
# At least this many sampled frames must contain a face for "кандидата видно".
FACE_VISIBLE_MIN_FRAMES = 3
# Transcript shorter than this (after strip) is treated as no speech for commission summary.
MIN_TRANSCRIPT_CHARS = 30
# Hard cap on how much of the source is processed (download / probe).
MAX_INPUT_DURATION_SEC = 3600
# Limit audio slice for Whisper cost/latency (first N seconds).
MAX_AUDIO_FOR_TRANSCRIPTION_SEC = 1200

COMMISSION_NO_TEXT = "Текст не обнаружен"
COMMISSION_VIDEO_TOO_LONG = "Видео длиннее 6 минут"
MAX_YOUTUBE_SUMMARY_DURATION_SEC = 6 * 60

# Минимум успешно извлечённых кадров для вывода комиссии «видно / не видно».
MIN_FRAMES_FOR_VISIBILITY_UI = 4

MEDIA_STATUS_READY = "ready"
MEDIA_STATUS_PARTIAL = "partial"
MEDIA_STATUS_FAILED = "failed"
