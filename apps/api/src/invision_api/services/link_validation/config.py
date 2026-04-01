from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LinkValidationConfig:
    allowed_schemes: tuple[str, ...] = ("http", "https")
    denied_schemes: tuple[str, ...] = ("javascript", "data", "file")
    deny_hosts: tuple[str, ...] = ("localhost",)
    allow_hosts: tuple[str, ...] = ()
    max_redirects: int = 5
    connect_timeout_sec: float = 3.0
    read_timeout_sec: float = 5.0
    retry_attempts: int = 2
    retry_backoff_sec: float = 0.25
    retry_jitter_sec: float = 0.15
    enable_private_ip_guard: bool = True
    auto_prepend_https: bool = True
    file_extensions: tuple[str, ...] = field(
        default_factory=lambda: (
            ".pdf",
            ".doc",
            ".docx",
            ".ppt",
            ".pptx",
            ".xls",
            ".xlsx",
            ".zip",
            ".rar",
            ".7z",
            ".txt",
            ".csv",
            ".mp4",
            ".avi",
            ".mov",
            ".mkv",
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        )
    )
