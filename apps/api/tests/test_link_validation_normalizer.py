from invision_api.services.link_validation.config import LinkValidationConfig
from invision_api.services.link_validation.normalizer import normalize_url


def test_normalize_autoprepends_https() -> None:
    out = normalize_url("example.com/path", LinkValidationConfig())
    assert out.normalized_url == "https://example.com/path"
    assert out.errors == []


def test_normalize_rejects_empty() -> None:
    out = normalize_url("  ", LinkValidationConfig())
    assert out.normalized_url is None
    assert out.errors
