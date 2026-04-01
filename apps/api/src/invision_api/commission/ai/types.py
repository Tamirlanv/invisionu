"""Domain-shaped structures for commission AI (deterministic + compact payload)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TextBlockFeatures:
    """Per-text-block algorithmic features (motivation, path, essay, etc.)."""

    block_key: str
    normalized_text: str
    stats: dict[str, Any]
    heuristics: dict[str, float]
    tags: list[str]
    key_fragments: list[str]
    flags: dict[str, bool]  # is_too_short, is_repetitive, ...
    explain_reasons: tuple[str, ...]


@dataclass(frozen=True)
class AggregateCandidateSignals:
    """Rolled-up booleans + human-readable reasons for explainability."""

    section_coverage: dict[str, bool]
    flags: dict[str, bool]
    reasons: tuple[str, ...]
    numeric_rollup: dict[str, float]


@dataclass(frozen=True)
class CandidateContext:
    """Projection + minimal identity for the LLM (no raw PII dumps)."""

    full_name: str | None
    program: str | None
    city: str | None
    age: int | None
    submitted_at_iso: str | None


@dataclass(frozen=True)
class CommissionAISourceBundle:
    """Everything collected from DB before preprocessing."""

    application_id: str
    candidate: CandidateContext
    section_payloads: dict[str, Any]
    reviewer_context: dict[str, Any] | None
