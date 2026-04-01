from __future__ import annotations

from urllib.parse import urlsplit

from invision_api.services.link_validation.config import LinkValidationConfig
from invision_api.services.link_validation.types import ClassificationResult, ProviderType, ResourceType


def _provider_from_host(hostname: str) -> ProviderType:
    host = hostname.lower()
    if host in {"drive.google.com"}:
        return "google_drive"
    if host in {"docs.google.com"}:
        return "google_docs"
    if host.endswith("dropbox.com") or host == "db.tt":
        return "dropbox"
    if host.endswith("onedrive.live.com") or host.endswith("1drv.ms"):
        return "onedrive"
    if host.endswith("youtube.com") or host == "youtu.be":
        return "youtube"
    if host.endswith("vimeo.com"):
        return "vimeo"
    return "generic"


def _resource_from_context(provider: ProviderType, url: str, content_type: str | None, config: LinkValidationConfig) -> ResourceType:
    if provider in {"google_drive", "google_docs", "dropbox", "onedrive"}:
        return "cloud_resource"
    if provider in {"youtube", "vimeo"}:
        return "video"

    lower_url = url.lower()
    if any(lower_url.endswith(ext) for ext in config.file_extensions):
        return "file"
    if content_type:
        if content_type.startswith("video/"):
            return "video"
        if (
            content_type.startswith("application/")
            or content_type.startswith("image/")
            or content_type.startswith("audio/")
        ) and "html" not in content_type:
            return "file"
        if "text/html" in content_type:
            return "web_page"
    return "web_page"


def classify_url(url: str, content_type: str | None, config: LinkValidationConfig) -> ClassificationResult:
    split = urlsplit(url)
    provider = _provider_from_host(split.hostname or "")
    resource_type = _resource_from_context(provider, url, content_type, config)

    hints: dict[str, str] = {}
    path = split.path
    if provider == "google_drive":
        if "/file/d/" in path:
            hints["drive_pattern"] = "file_view"
        elif "/uc" in path:
            hints["drive_pattern"] = "direct_download"
    if provider == "google_docs":
        if "/document/d/" in path:
            hints["docs_type"] = "document"
        elif "/spreadsheets/d/" in path:
            hints["docs_type"] = "spreadsheets"
        elif "/presentation/d/" in path:
            hints["docs_type"] = "presentation"

    return ClassificationResult(provider=provider, resource_type=resource_type, hints=hints)
