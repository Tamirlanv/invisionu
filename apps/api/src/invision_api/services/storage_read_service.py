from __future__ import annotations

import logging
from uuid import UUID

import httpx

from invision_api.core.config import get_settings
from invision_api.services.storage import get_storage

logger = logging.getLogger(__name__)


def _fetch_via_proxy(*, document_id: UUID, base_url: str, shared_secret: str, timeout_seconds: float) -> bytes:
    endpoint = (
        f"{base_url.rstrip('/')}/api/v1/internal/processing/storage/documents/{document_id}/file"
    )
    headers = {"X-Storage-Proxy-Secret": shared_secret}
    with httpx.Client(timeout=timeout_seconds) as client:
        resp = client.get(endpoint, headers=headers)
    if resp.status_code >= 300:
        detail = (resp.text or "")[:300]
        raise OSError(f"storage proxy HTTP {resp.status_code}: {detail}")
    return resp.content


def read_document_bytes_with_fallback(*, document_id: UUID, storage_key: str) -> bytes:
    """Read bytes from local storage and optionally fallback to API storage-proxy."""
    settings = get_settings()
    storage = get_storage()

    try:
        return storage.read_bytes(storage_key)
    except (FileNotFoundError, OSError) as local_exc:
        logger.warning(
            "storage_local_miss document_id=%s storage_key=%s mode=%s error=%s",
            document_id,
            storage_key,
            settings.storage_read_mode,
            str(local_exc)[:300],
        )
        if settings.storage_read_mode != "local_then_proxy":
            raise
        if not settings.storage_proxy_base_url:
            raise OSError("STORAGE_PROXY_BASE_URL is required for local_then_proxy mode") from local_exc
        if not settings.storage_proxy_shared_secret:
            raise OSError("STORAGE_PROXY_SHARED_SECRET is required for local_then_proxy mode") from local_exc

        logger.info(
            "storage_proxy_attempt document_id=%s storage_key=%s proxy_base=%s",
            document_id,
            storage_key,
            settings.storage_proxy_base_url,
        )
        try:
            data = _fetch_via_proxy(
                document_id=document_id,
                base_url=settings.storage_proxy_base_url,
                shared_secret=settings.storage_proxy_shared_secret,
                timeout_seconds=settings.storage_proxy_timeout_seconds,
            )
            logger.info(
                "storage_proxy_result document_id=%s storage_key=%s status=ok bytes=%s",
                document_id,
                storage_key,
                len(data),
            )
            return data
        except Exception as proxy_exc:
            logger.error(
                "storage_proxy_result document_id=%s storage_key=%s status=error error=%s",
                document_id,
                storage_key,
                str(proxy_exc)[:300],
            )
            raise OSError(str(proxy_exc)) from proxy_exc
