from __future__ import annotations

from invision_api.services.link_validation.types import AvailabilityResult, ClassificationResult, HttpProbeResult


def determine_availability(
    is_valid_format: bool,
    probe: HttpProbeResult,
    classification: ClassificationResult,
    cloud_errors: list[str],
) -> AvailabilityResult:
    warnings: list[str] = []
    errors: list[str] = []

    if not is_valid_format:
        return AvailabilityResult(is_reachable=False, status="invalid", errors=["Invalid URL format"])
    if probe.timeout:
        return AvailabilityResult(is_reachable=False, status="timeout", warnings=["Request timed out"])
    if probe.network_error:
        return AvailabilityResult(is_reachable=False, status="unreachable", errors=[probe.error_text or "Network error"])

    code = probe.status_code
    if code is None:
        return AvailabilityResult(is_reachable=False, status="unknown", warnings=["No HTTP status code"])
    if cloud_errors:
        return AvailabilityResult(is_reachable=False, status="private_access", errors=cloud_errors)
    if code in {401, 407}:
        return AvailabilityResult(is_reachable=False, status="private_access", warnings=["Authorization required"])
    if code in {403}:
        return AvailabilityResult(is_reachable=False, status="forbidden", errors=["Access forbidden"])
    if code in {404, 410}:
        return AvailabilityResult(is_reachable=False, status="unreachable", errors=["Resource not found"])
    if 500 <= code <= 599:
        return AvailabilityResult(is_reachable=False, status="unreachable", errors=["Server error from target"])
    if 200 <= code <= 399:
        if classification.resource_type == "unknown":
            warnings.append("Resource type could not be confidently identified")
        return AvailabilityResult(is_reachable=True, status="reachable", warnings=warnings)
    return AvailabilityResult(is_reachable=False, status="unknown", warnings=["Unhandled status code class"])
