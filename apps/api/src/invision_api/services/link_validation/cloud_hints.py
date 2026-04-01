from __future__ import annotations

from urllib.parse import urlsplit

from invision_api.services.link_validation.types import ClassificationResult, HttpProbeResult


def cloud_access_hints(classification: ClassificationResult, probe: HttpProbeResult) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []

    if classification.provider not in {"google_drive", "google_docs", "dropbox", "onedrive"}:
        return warnings, errors

    if probe.status_code is None:
        warnings.append("Cloud link was not fully checked due to network issue")
        return warnings, errors

    status = probe.status_code
    final_url = probe.final_url or ""
    final_path = urlsplit(final_url).path.lower()
    lower_ct = (probe.content_type or "").lower()

    if status in {401}:
        warnings.append("Cloud resource likely requires login")
    elif status in {403}:
        errors.append("Cloud resource access denied")
    elif status in {404, 410}:
        errors.append("Cloud resource is missing")
    elif status == 429:
        warnings.append("Cloud provider quota or rate limit exceeded")

    if classification.provider == "google_drive":
        if "/file/d/" not in final_path and "/uc" not in final_path and "/drive/folders/" not in final_path:
            warnings.append("Google Drive sharing mode is unusual or unsupported")
    if classification.provider == "google_docs":
        if not any(chunk in final_path for chunk in ("/document/d/", "/spreadsheets/d/", "/presentation/d/")):
            warnings.append("Google Docs sharing mode may be unsupported")
    if "text/html" in lower_ct and status == 200 and any(x in final_url.lower() for x in ("login", "signin", "auth")):
        warnings.append("Cloud link resolved to auth page, may require private access")

    return warnings, errors
