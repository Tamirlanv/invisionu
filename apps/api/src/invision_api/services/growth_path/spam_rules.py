"""Rule-based spam / low-effort checks (no LLM)."""

from __future__ import annotations

from dataclasses import dataclass

from invision_api.services.growth_path.config import (
    MAX_REPEATED_SENTENCE_RATIO,
    SPAM_PHRASES,
    UNIQUE_WORD_RATIO_LOW,
)
from invision_api.services.growth_path.heuristics import repetitive_score
from invision_api.services.growth_path.stats import compute_text_stats


@dataclass(frozen=True)
class SpamCheckResult:
    ok: bool
    reasons: tuple[str, ...]


def check_answer_spam(normalized_text: str) -> SpamCheckResult:
    """Return ok=False if text should be rejected for committee quality gates."""
    reasons: list[str] = []
    t = normalized_text.lower()

    for phrase in SPAM_PHRASES:
        if phrase in t:
            reasons.append("spam_phrase")

    stats = compute_text_stats(normalized_text)
    if stats.word_count >= 8 and stats.unique_word_ratio < UNIQUE_WORD_RATIO_LOW:
        reasons.append("low_lexical_diversity")

    if repetitive_score(t) >= MAX_REPEATED_SENTENCE_RATIO and stats.sentence_count >= 3:
        reasons.append("high_repetition")

    ok = len(reasons) == 0
    return SpamCheckResult(ok=ok, reasons=tuple(reasons))
