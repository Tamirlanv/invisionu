"""Build compact JSON-serializable payload for the LLM (no raw logs / secrets)."""

from __future__ import annotations

from typing import Any

from invision_api.commission.ai.signals.aggregate import AggregateCandidateSignals, aggregate_to_serializable
from invision_api.commission.ai.types import CommissionAISourceBundle, TextBlockFeatures


def _trim(s: str, max_chars: int) -> str:
    t = (s or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1] + "…"


def _block_compact(b: TextBlockFeatures, *, preview_chars: int = 4000) -> dict[str, Any]:
    return {
        "block_key": b.block_key,
        "stats": b.stats,
        "heuristics": b.heuristics,
        "tags": b.tags,
        "key_fragments": b.key_fragments[:5],
        "flags": b.flags,
        "text_preview": _trim(b.normalized_text, preview_chars),
    }


def build_compact_ai_payload(
    *,
    bundle: CommissionAISourceBundle,
    blocks: dict[str, TextBlockFeatures],
    aggregate_signals: AggregateCandidateSignals,
    algorithmic_explainability_hints: list[str],
    algorithmic_confidence_base: int,
) -> dict[str, Any]:
    sp = bundle.section_payloads
    test_profile = sp.get("structured_test_profile") or {}
    return {
        "candidateContext": {
            "full_name": bundle.candidate.full_name,
            "program": bundle.candidate.program,
            "city": bundle.candidate.city,
            "age": bundle.candidate.age,
            "submitted_at_iso": bundle.candidate.submitted_at_iso,
        },
        "structuredTestProfile": test_profile,
        "motivation": _block_compact(blocks["motivation"]),
        "path": _block_compact(blocks["path"]),
        "essay": _block_compact(blocks["essay"]),
        "portfolio": sp.get("portfolio_compact") or {},
        "optionalReviewerContext": bundle.reviewer_context,
        "aggregateSignals": aggregate_to_serializable(aggregate_signals),
        "algorithmicExplainabilityHints": algorithmic_explainability_hints[:40],
        "algorithmicConfidenceBase": algorithmic_confidence_base,
    }
