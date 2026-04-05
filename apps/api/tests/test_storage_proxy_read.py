from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from invision_api.core.config import get_settings
from invision_api.services.storage_read_service import read_document_bytes_with_fallback


def _clear_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_settings_cache_after_test():
    _clear_settings_cache()
    try:
        yield
    finally:
        _clear_settings_cache()


def test_storage_read_local_success_without_proxy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    key = "app/file.pdf"
    p = tmp_path / key
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"local-ok")

    monkeypatch.setenv("UPLOAD_ROOT", str(tmp_path))
    monkeypatch.setenv("STORAGE_READ_MODE", "local_then_proxy")
    monkeypatch.setenv("STORAGE_PROXY_BASE_URL", "http://example.local")
    monkeypatch.setenv("STORAGE_PROXY_SHARED_SECRET", "secret")
    _clear_settings_cache()

    data = read_document_bytes_with_fallback(document_id=uuid4(), storage_key=key)
    assert data == b"local-ok"


def test_storage_read_local_miss_uses_proxy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: dict[str, str] = {}
    doc_id = uuid4()

    class _Resp:
        status_code = 200
        content = b"remote-ok"
        text = "ok"

    class _Client:
        def __init__(self, timeout: float):
            calls["timeout"] = str(timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def get(self, url: str, headers: dict[str, str]):
            calls["url"] = url
            calls["secret"] = headers.get("X-Storage-Proxy-Secret", "")
            return _Resp()

    monkeypatch.setenv("UPLOAD_ROOT", str(tmp_path))
    monkeypatch.setenv("STORAGE_READ_MODE", "local_then_proxy")
    monkeypatch.setenv("STORAGE_PROXY_BASE_URL", "http://api.internal:8000")
    monkeypatch.setenv("STORAGE_PROXY_SHARED_SECRET", "top-secret")
    monkeypatch.setenv("STORAGE_PROXY_TIMEOUT_SECONDS", "7")
    monkeypatch.setattr("invision_api.services.storage_read_service.httpx.Client", _Client)
    _clear_settings_cache()

    data = read_document_bytes_with_fallback(document_id=doc_id, storage_key="missing/file.pdf")
    assert data == b"remote-ok"
    assert calls["secret"] == "top-secret"
    assert calls["timeout"] == "7.0"
    assert calls["url"].endswith(f"/api/v1/internal/processing/storage/documents/{doc_id}/file")


def test_storage_read_local_miss_proxy_http_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _Resp:
        status_code = 404
        content = b""
        text = "not found"

    class _Client:
        def __init__(self, timeout: float):
            _ = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def get(self, _url: str, headers: dict[str, str]):
            _ = headers
            return _Resp()

    monkeypatch.setenv("UPLOAD_ROOT", str(tmp_path))
    monkeypatch.setenv("STORAGE_READ_MODE", "local_then_proxy")
    monkeypatch.setenv("STORAGE_PROXY_BASE_URL", "http://api.internal:8000")
    monkeypatch.setenv("STORAGE_PROXY_SHARED_SECRET", "top-secret")
    monkeypatch.setattr("invision_api.services.storage_read_service.httpx.Client", _Client)
    _clear_settings_cache()

    with pytest.raises(OSError):
        read_document_bytes_with_fallback(document_id=uuid4(), storage_key="missing/file.pdf")
