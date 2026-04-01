"""Rule-based markers for reflection, action, time, concrete detail."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Russian + English patterns (lowercase text).
_ACTION_PATTERNS = (
    r"\b(организовал|организовала|создал|создала|запустил|запустила|инициировал|инициировала|улучшил|улучшила)\b",
    r"\b(organized|started|led|improved|launched|initiated)\b",
)
_REFLECTION_PATTERNS = (
    r"\b(понял|поняла|осознал|осознала|размышлял|размышляла|вывод|урок)\b",
    r"\b(realized|learned|reflected|understood)\b",
)
_TIME_PATTERNS = (
    r"\b(в\s+20\d{2}|год|месяц|неделю|два года|три года|несколько лет)\b",
    r"\b(years?|months?|weeks?|since|during)\b",
)
_CONCRETE_PATTERNS = (
    r"\d+[\s]*(человек|участник|студент|руб|тенге|\$|eur|kg|км)",
    r"\b\d{1,2}\s*%|\b\d+\s*из\s*\d+",
)


@dataclass(frozen=True)
class HeuristicMarkers:
    action_score: float
    reflection_score: float
    time_score: float
    concrete_score: float
    repetitive_score: float


def _count_matches(patterns: tuple[str, ...], text_lower: str) -> int:
    n = 0
    for p in patterns:
        n += len(re.findall(p, text_lower, flags=re.IGNORECASE))
    return n


def repetitive_score(text_lower: str) -> float:
    """High if few unique sentences dominate."""
    sentences = [s.strip() for s in re.split(r"[.!?…]+", text_lower) if s.strip()]
    if len(sentences) < 2:
        return 0.0
    from collections import Counter

    c = Counter(sentences)
    most = c.most_common(1)[0][1]
    return min(1.0, most / len(sentences))


def compute_heuristics(normalized_text: str) -> HeuristicMarkers:
    t = normalized_text.lower()
    action = min(1.0, _count_matches(_ACTION_PATTERNS, t) / 3.0)
    refl = min(1.0, _count_matches(_REFLECTION_PATTERNS, t) / 3.0)
    time_m = min(1.0, _count_matches(_TIME_PATTERNS, t) / 2.0)
    conc = min(1.0, _count_matches(_CONCRETE_PATTERNS, t) / 2.0)
    rep = repetitive_score(t)
    return HeuristicMarkers(
        action_score=round(action, 3),
        reflection_score=round(refl, 3),
        time_score=round(time_m, 3),
        concrete_score=round(conc, 3),
        repetitive_score=round(rep, 3),
    )
