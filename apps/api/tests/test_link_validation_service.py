from invision_api.services.link_validation.service import validate_candidate_link
from invision_api.services.link_validation.types import HttpProbeResult, LinkValidationRequest


class _StubProbeClient:
    def probe(self, url: str) -> HttpProbeResult:
        _ = url
        return HttpProbeResult(
            final_url="https://drive.google.com/file/d/abc/view",
            status_code=200,
            content_type="text/html",
            content_length=1024,
            redirected=True,
            redirect_count=1,
            response_time_ms=88,
        )


class _StubSession:
    def __init__(self) -> None:
        self.added = []
        self.commits = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        self.commits += 1


def test_service_runs_full_pipeline_with_stub_probe() -> None:
    db = _StubSession()
    out = validate_candidate_link(
        db=db,  # type: ignore[arg-type]
        payload=LinkValidationRequest(url="drive.google.com/file/d/abc/view"),
        probe_client=_StubProbeClient(),  # type: ignore[arg-type]
    )
    assert out.isValidFormat is True
    assert out.isReachable is True
    assert out.provider == "google_drive"
    assert out.resourceType == "cloud_resource"
    assert db.commits == 1
    assert db.added
