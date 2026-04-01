from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from invision_api.services.link_validation.config import LinkValidationConfig
from invision_api.services.link_validation.types import NormalizedUrl


def normalize_url(raw_url: str, config: LinkValidationConfig) -> NormalizedUrl:
    text = (raw_url or "").strip()
    if not text:
        return NormalizedUrl(original_url=raw_url, normalized_url=None, errors=["URL is empty"])

    normalized = text
    if "://" not in normalized and config.auto_prepend_https:
        normalized = f"https://{normalized}"

    try:
        split = urlsplit(normalized)
    except ValueError:
        return NormalizedUrl(original_url=raw_url, normalized_url=None, errors=["Malformed URL"])

    scheme = split.scheme.lower()
    host = (split.hostname or "").strip()
    if not host:
        return NormalizedUrl(original_url=raw_url, normalized_url=None, errors=["Hostname is missing"])

    try:
        host_ascii = host.encode("idna").decode("ascii")
    except UnicodeError:
        return NormalizedUrl(original_url=raw_url, normalized_url=None, errors=["Hostname is invalid"])

    netloc = host_ascii
    if split.port:
        netloc = f"{host_ascii}:{split.port}"

    cleaned_path = split.path or "/"
    result = urlunsplit((scheme, netloc, cleaned_path, split.query, ""))
    return NormalizedUrl(original_url=raw_url, normalized_url=result)
