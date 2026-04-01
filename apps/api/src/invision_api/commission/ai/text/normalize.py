"""Text normalization — reuse growth_path rules."""

from __future__ import annotations

import re

from invision_api.services.growth_path.normalize import normalize_growth_text

__all__ = ["normalize_commission_text", "strip_control_chars"]


def strip_control_chars(s: str) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)


def normalize_commission_text(raw: str) -> str:
    return normalize_growth_text(strip_control_chars(raw or ""))
