"""Key fragments: scored sentences (length + simple markers)."""

from __future__ import annotations

import re

from invision_api.commission.ai.text.heuristics import compute_heuristics
from invision_api.commission.ai.text.stats import compute_text_stats

_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+|[\n]+")


def extract_key_fragments(normalized_text: str, *, max_fragments: int = 3) -> list[str]:
    if not normalized_text.strip():
        return []
    parts = [s.strip() for s in _SENT_SPLIT.split(normalized_text) if s.strip()]
    if not parts:
        return []
    heur = compute_heuristics(normalized_text)
    bonus = (
        float(heur.action_score) * 2.0
        + float(heur.reflection_score) * 1.5
        + float(heur.concrete_score) * 2.0
        - float(heur.repetitive_score) * 3.0
    )
    scored: list[tuple[float, str]] = []
    for s in parts:
        st = compute_text_stats(s)
        base = min(120.0, float(len(s))) * 0.1 + float(st.word_count) * 0.3
        score = base + bonus
        scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[str] = []
    for _, s in scored:
        if s not in out:
            out.append(s)
        if len(out) >= max_fragments:
            break
    return out
