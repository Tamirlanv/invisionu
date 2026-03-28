import os
import uuid
from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    def put(self, *, application_id: uuid.UUID, original_filename: str, data: bytes, content_type: str) -> str:
        """Persist bytes; return storage key (path relative to root or opaque id)."""

    def absolute_path(self, storage_key: str) -> Path:
        """Resolve storage key to local path for serving/admin."""

    def delete(self, storage_key: str) -> None: ...


class LocalStorageBackend:
    def __init__(self, root: str) -> None:
        self._root = Path(root)

    def put(self, *, application_id: uuid.UUID, original_filename: str, data: bytes, content_type: str) -> str:
        ext = Path(original_filename).suffix[:16] or ""
        safe = f"{uuid.uuid4().hex}{ext}"
        rel = f"{application_id}/{safe}"
        dest = self._root / application_id
        dest.mkdir(parents=True, exist_ok=True)
        full = self._root / rel
        full.write_bytes(data)
        return rel.replace("\\", "/")

    def absolute_path(self, storage_key: str) -> Path:
        return (self._root / storage_key).resolve()

    def delete(self, storage_key: str) -> None:
        p = self.absolute_path(storage_key)
        if p.is_file():
            p.unlink()


def get_storage() -> LocalStorageBackend:
    from invision_api.core.config import get_settings

    root = get_settings().upload_root
    Path(root).mkdir(parents=True, exist_ok=True)
    return LocalStorageBackend(root)
