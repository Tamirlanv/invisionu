"""Extractive key sentences (rule-based, no LLM)."""

from __future__ import annotations

import re


def extract_key_sentences(normalized_text: str, max_sentences: int = 2) -> list[str]:
    """Pick longest sentences by character length (simple proxy for substance)."""
    parts = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", normalized_text) if s.strip()]
    if not parts:
        return []
    parts.sort(key=len, reverse=True)
    return parts[:max_sentences]
