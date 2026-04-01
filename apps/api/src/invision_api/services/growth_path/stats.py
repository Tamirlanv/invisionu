"""Deterministic text statistics for growth answers."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Words: Latin letters, Cyrillic letters, digits glued; split on non-word.
_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-'][A-Za-zА-Яа-яЁё0-9]+)*", re.UNICODE)
_SENT_SPLIT = re.compile(r"[.!?…]+\s*|\n+")


@dataclass(frozen=True)
class TextStats:
    char_count: int
    word_count: int
    sentence_count: int
    paragraph_count: int
    avg_sentence_length: float
    unique_word_ratio: float


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]


def compute_text_stats(normalized_text: str) -> TextStats:
    if not normalized_text:
        return TextStats(0, 0, 0, 0, 0.0, 0.0)

    chars = len(normalized_text)
    tokens = [m.group(0).lower() for m in _TOKEN_RE.finditer(normalized_text)]
    word_count = len(tokens)
    unique = set(tokens)
    unique_ratio = (len(unique) / word_count) if word_count else 0.0

    paras = _paragraphs(normalized_text)
    paragraph_count = max(1, len(paras))

    # Rough sentence split
    raw_sents = [s.strip() for s in _SENT_SPLIT.split(normalized_text) if s.strip()]
    if not raw_sents:
        raw_sents = [normalized_text]
    sentence_count = len(raw_sents)
    avg_sent = (word_count / sentence_count) if sentence_count else 0.0

    return TextStats(
        char_count=chars,
        word_count=word_count,
        sentence_count=sentence_count,
        paragraph_count=paragraph_count,
        avg_sentence_length=round(avg_sent, 2),
        unique_word_ratio=round(unique_ratio, 4),
    )
