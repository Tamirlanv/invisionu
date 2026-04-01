"""Aggregate section-level signals."""

from __future__ import annotations

from typing import Any

from invision_api.services.growth_path.heuristics import HeuristicMarkers, compute_heuristics
from invision_api.services.growth_path.stats import TextStats, compute_text_stats


def aggregate_section_signals(
    per_question: dict[str, dict[str, Any]],
) -> dict[str, float]:
    """Roll up initiative, resilience, growth, responsibility, concrete experience [0..1]."""
    initiative = 0.0
    resilience = 0.0
    growth = 0.0
    responsibility = 0.0
    concrete = 0.0
    n = max(1, len(per_question))

    for qid, block in per_question.items():
        h = block.get("heuristics") or {}
        initiative += float(h.get("action_score", 0))
        resilience += float(h.get("reflection_score", 0)) * 0.5 + (1.0 - float(h.get("repetitive_score", 0))) * 0.3
        growth += float(h.get("reflection_score", 0)) * 0.4 + float(h.get("time_score", 0)) * 0.3
        responsibility += float(h.get("action_score", 0)) * 0.6
        concrete += float(h.get("concrete_score", 0))

    return {
        "initiative": round(min(1.0, initiative / n), 3),
        "resilience": round(min(1.0, resilience / n), 3),
        "growth": round(min(1.0, growth / n), 3),
        "responsibility": round(min(1.0, responsibility / n), 3),
        "concrete_experience": round(min(1.0, concrete / n), 3),
    }


def build_per_question_block(
    *,
    qid: str,
    normalized_text: str,
) -> dict[str, Any]:
    stats: TextStats = compute_text_stats(normalized_text)
    heur: HeuristicMarkers = compute_heuristics(normalized_text)
    return {
        "stats": {
            "char_count": stats.char_count,
            "word_count": stats.word_count,
            "sentence_count": stats.sentence_count,
            "paragraph_count": stats.paragraph_count,
            "avg_sentence_length": stats.avg_sentence_length,
            "unique_word_ratio": stats.unique_word_ratio,
        },
        "heuristics": {
            "action_score": heur.action_score,
            "reflection_score": heur.reflection_score,
            "time_score": heur.time_score,
            "concrete_score": heur.concrete_score,
            "repetitive_score": heur.repetitive_score,
        },
    }
