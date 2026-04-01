"""Algorithmic base confidence + bounded LLM delta."""

from __future__ import annotations

from invision_api.commission.ai.signals.aggregate import AggregateCandidateSignals
from invision_api.commission.ai.types import TextBlockFeatures


def algorithmic_confidence_base(
    *,
    blocks: dict[str, TextBlockFeatures],
    aggregate: AggregateCandidateSignals,
) -> tuple[int, list[str]]:
    """
    Return C0 in [0, 100] and deterministic explainability strings.
    """
    notes: list[str] = []
    score = 55

    filled = sum(1 for b in blocks.values() if b.stats.get("word_count", 0) >= 80)
    score += min(20, filled * 5)
    notes.append(f"Заполненность длинных текстовых блоков: {filled}/{len(blocks)}")

    for name, b in blocks.items():
        ur = float(b.stats.get("unique_word_ratio") or 0.0)
        if ur and ur < 0.25 and b.stats.get("word_count", 0) > 30:
            score -= 5
            notes.append(f"{name}: низкая лексическая вариативность")

    if aggregate.flags.get("sparse_texts"):
        score -= 12
        notes.append("Штраф: несколько блоков слишком короткие")
    if aggregate.flags.get("repetitive_language"):
        score -= 8
        notes.append("Штраф: повторяемость формулировок")
    if aggregate.flags.get("missing_motivation"):
        score -= 10
        notes.append("Штраф: нет мотивационного текста")
    if aggregate.flags.get("missing_path"):
        score -= 8
        notes.append("Штраф: нет текста пути роста")

    # Light consistency: numeric rollup vs flags
    nr = aggregate.numeric_rollup
    if nr.get("concrete_experience", 0) >= 0.55:
        score += 5
        notes.append("Бонус: заметная конкретика в формулировках")

    score = max(0, min(100, int(round(score))))
    return score, notes


def final_confidence(*, c0: int, llm_delta: int | None, completeness_fallback: float) -> tuple[int, int]:
    """
    C = clamp(C0 + d, 0, 100). If llm_delta is None, map completeness_fallback [0..1] to small integer delta.
    """
    d = llm_delta
    if d is None:
        d = int(round((completeness_fallback - 0.5) * 10))
        d = max(-15, min(15, d))
    else:
        d = max(-15, min(15, int(d)))
    return max(0, min(100, c0 + d)), d


def completeness_score(blocks: dict[str, TextBlockFeatures]) -> float:
    """0..1 from word counts."""
    if not blocks:
        return 0.0
    parts = []
    for b in blocks.values():
        wc = int(b.stats.get("word_count") or 0)
        parts.append(min(1.0, wc / 200.0))
    return round(sum(parts) / len(parts), 3)
