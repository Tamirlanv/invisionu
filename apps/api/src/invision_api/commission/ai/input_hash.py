"""Canonical input hashing for regeneration (deterministic inputs + version)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))


def compute_input_hash(*, parts: dict[str, Any], source_data_version: str) -> str:
    payload = {"source_data_version": source_data_version, "parts": parts}
    raw = canonical_json(payload)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
