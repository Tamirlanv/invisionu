from invision_api.services.link_validation.config import LinkValidationConfig
from invision_api.services.link_validation.validator import validate_url_format


def test_validator_accepts_http_https() -> None:
    parsed, warnings, errors = validate_url_format("https://example.com/a", LinkValidationConfig())
    assert parsed is not None
    assert warnings == []
    assert errors == []


def test_validator_rejects_javascript_scheme() -> None:
    parsed, _, errors = validate_url_format("javascript://example.com/x", LinkValidationConfig())
    assert parsed is None
    assert errors
