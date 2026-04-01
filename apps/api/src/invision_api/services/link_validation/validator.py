from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

from invision_api.services.link_validation.config import LinkValidationConfig
from invision_api.services.link_validation.types import ParsedUrlContext

_HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9.-]+(?<!-)$")


def _is_ip_private(hostname: str) -> bool:
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local


def validate_url_format(normalized_url: str, config: LinkValidationConfig) -> tuple[ParsedUrlContext | None, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        split = urlsplit(normalized_url)
    except ValueError:
        return None, warnings, ["Malformed URL"]

    scheme = split.scheme.lower().strip()
    hostname = (split.hostname or "").lower().strip()
    path = split.path or "/"
    query = split.query

    if scheme in config.denied_schemes:
        errors.append(f"Scheme {scheme} is denied")
    if scheme not in config.allowed_schemes:
        errors.append(f"Scheme {scheme} is not supported")
    if not hostname:
        errors.append("Hostname is missing")
    if hostname and not _HOSTNAME_RE.match(hostname):
        errors.append("Hostname is invalid")
    if hostname in config.deny_hosts:
        errors.append("Hostname is denied")
    if config.allow_hosts and hostname not in config.allow_hosts:
        errors.append("Hostname is not in allowlist")
    if config.enable_private_ip_guard and hostname and _is_ip_private(hostname):
        errors.append("Private or loopback address is not allowed")
    if any(x in normalized_url.lower() for x in ("\x00", "\r", "\n")):
        errors.append("URL contains forbidden control characters")
    if len(path) > 2048:
        warnings.append("Path is unusually long")

    if errors:
        return None, warnings, errors

    return (
        ParsedUrlContext(
            scheme=scheme,
            hostname=hostname,
            path=path,
            query=query,
            normalized_url=normalized_url,
        ),
        warnings,
        errors,
    )
