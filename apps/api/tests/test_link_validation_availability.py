from invision_api.services.link_validation.availability import determine_availability
from invision_api.services.link_validation.types import ClassificationResult, HttpProbeResult


def _base_classification() -> ClassificationResult:
    return ClassificationResult(provider="generic", resource_type="web_page")


def test_availability_reachable_200() -> None:
    res = determine_availability(
        True,
        HttpProbeResult(
            final_url="https://example.com",
            status_code=200,
            content_type="text/html",
            content_length=None,
            redirected=False,
            redirect_count=0,
            response_time_ms=123,
        ),
        _base_classification(),
        [],
    )
    assert res.status == "reachable"
    assert res.is_reachable is True


def test_availability_private_access_on_401() -> None:
    res = determine_availability(
        True,
        HttpProbeResult(
            final_url="https://example.com/login",
            status_code=401,
            content_type="text/html",
            content_length=None,
            redirected=False,
            redirect_count=0,
            response_time_ms=50,
        ),
        _base_classification(),
        [],
    )
    assert res.status == "private_access"
    assert res.is_reachable is False
