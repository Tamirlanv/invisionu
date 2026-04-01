"""Aggregate per-block features into section-level signals."""

from __future__ import annotations

from typing import Any

from invision_api.commission.ai.types import AggregateCandidateSignals, TextBlockFeatures


def aggregate_candidate_signals(
    blocks: dict[str, TextBlockFeatures],
) -> AggregateCandidateSignals:
    coverage = {k: bool(b.normalized_text.strip()) for k, b in blocks.items()}
    reasons: list[str] = []
    for b in blocks.values():
        reasons.extend(b.explain_reasons)

    initiative = 0.0
    resilience = 0.0
    growth = 0.0
    concrete = 0.0
    n = max(1, len(blocks))
    for b in blocks.values():
        h = b.heuristics
        initiative += float(h.get("action_score", 0))
        resilience += float(h.get("reflection_score", 0)) * 0.5 + (1.0 - float(h.get("repetitive_score", 0))) * 0.3
        growth += float(h.get("reflection_score", 0)) * 0.4 + float(h.get("time_score", 0)) * 0.3
        concrete += float(h.get("concrete_score", 0))

    numeric_rollup = {
        "initiative": round(min(1.0, initiative / n), 3),
        "resilience": round(min(1.0, resilience / n), 3),
        "growth": round(min(1.0, growth / n), 3),
        "concrete_experience": round(min(1.0, concrete / n), 3),
    }

    any_repetitive = any(b.flags.get("is_repetitive") for b in blocks.values())
    many_short = sum(1 for b in blocks.values() if b.flags.get("is_too_short") or b.flags.get("is_very_short"))
    flags: dict[str, bool] = {
        "sparse_texts": many_short >= 2,
        "repetitive_language": any_repetitive,
        "missing_motivation": not coverage.get("motivation"),
        "missing_path": not coverage.get("path"),
        "missing_essay": not coverage.get("essay"),
    }
    if flags["missing_motivation"]:
        reasons.append("Секция мотивации пуста или отсутствует")
    if flags["missing_path"]:
        reasons.append("Блок пути роста пуст или отсутствует")
    if flags["sparse_texts"]:
        reasons.append("Несколько текстовых блоков выглядят слишком короткими")
    if flags["repetitive_language"]:
        reasons.append("Замечена повышенная повторяемость формулировок")

    return AggregateCandidateSignals(
        section_coverage=coverage,
        flags=flags,
        reasons=tuple(dict.fromkeys(reasons)),
        numeric_rollup=numeric_rollup,
    )


def aggregate_to_serializable(agg: AggregateCandidateSignals) -> dict[str, Any]:
    return {
        "section_coverage": agg.section_coverage,
        "flags": agg.flags,
        "reasons": list(agg.reasons),
        "numeric_rollup": agg.numeric_rollup,
    }
