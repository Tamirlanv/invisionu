from invision_api.services.link_validation.classifier import classify_url
from invision_api.services.link_validation.config import LinkValidationConfig


def test_classifier_detects_google_docs() -> None:
    out = classify_url("https://docs.google.com/document/d/abc/view", "text/html", LinkValidationConfig())
    assert out.provider == "google_docs"
    assert out.resource_type == "cloud_resource"


def test_classifier_detects_video_provider() -> None:
    out = classify_url("https://youtu.be/abc123", "text/html", LinkValidationConfig())
    assert out.provider == "youtube"
    assert out.resource_type == "video"
