"""Build per-block deterministic features for commission texts."""

from __future__ import annotations

from typing import Any

from invision_api.commission.ai.text.fragments import extract_key_fragments
from invision_api.commission.ai.text.heuristics import compute_heuristics
from invision_api.commission.ai.text.normalize import normalize_commission_text
from invision_api.commission.ai.text.stats import compute_text_stats
from invision_api.commission.ai.text.tagging import rule_based_tags
from invision_api.commission.ai.types import TextBlockFeatures

# MVP thresholds (words).
_TOO_SHORT_WORDS = 40
_VERY_SHORT_WORDS = 15


def build_text_block_features(*, block_key: str, raw_text: str) -> TextBlockFeatures:
    normalized = normalize_commission_text(raw_text)
    stats = compute_text_stats(normalized)
    heur = compute_heuristics(normalized)
    tags = rule_based_tags(normalized.lower())
    frags = extract_key_fragments(normalized, max_fragments=3)

    wc = stats.word_count
    is_too_short = wc < _TOO_SHORT_WORDS and wc > 0
    is_very_short = wc < _VERY_SHORT_WORDS and wc > 0
    is_empty = wc == 0
    is_repetitive = float(heur.repetitive_score) >= 0.45 and stats.sentence_count >= 2

    flags = {
        "is_empty": is_empty,
        "is_very_short": is_very_short,
        "is_too_short": is_too_short,
        "is_repetitive": is_repetitive,
    }
    reasons: list[str] = []
    if is_empty:
        reasons.append(f"{block_key}: текст отсутствует")
    elif is_very_short:
        reasons.append(f"{block_key}: очень мало текста ({wc} слов)")
    elif is_too_short:
        reasons.append(f"{block_key}: текст короткий ({wc} слов)")
    if is_repetitive:
        reasons.append(f"{block_key}: высокая повторяемость формулировок")

    stats_d: dict[str, Any] = {
        "char_count": stats.char_count,
        "word_count": stats.word_count,
        "sentence_count": stats.sentence_count,
        "paragraph_count": stats.paragraph_count,
        "avg_sentence_length": stats.avg_sentence_length,
        "unique_word_ratio": stats.unique_word_ratio,
    }
    heur_d = {
        "action_score": heur.action_score,
        "reflection_score": heur.reflection_score,
        "time_score": heur.time_score,
        "concrete_score": heur.concrete_score,
        "repetitive_score": heur.repetitive_score,
    }
    return TextBlockFeatures(
        block_key=block_key,
        normalized_text=normalized,
        stats=stats_d,
        heuristics=heur_d,
        tags=tags,
        key_fragments=frags,
        flags=flags,
        explain_reasons=tuple(reasons),
    )
