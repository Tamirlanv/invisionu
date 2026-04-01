"""Lightweight rule-based tags (RU/EN keywords) — no heavy NLP."""

from __future__ import annotations

import re

# (tag_id, patterns) — matched case-insensitive on normalized lower text.
_TAG_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "leadership",
        (
            r"\bлидер",
            r"\bруковод",
            r"\bкоманда",
            r"\bорганиз",
            r"\bинициатив",
            r"\bleadership",
            r"\bleader\b",
            r"\bteam\b",
            r"\borganized\b",
        ),
    ),
    (
        "reflection",
        (
            r"\bпонял",
            r"\bпоняла",
            r"\bурок",
            r"\bвывод",
            r"\bосознал",
            r"\breflection",
            r"\blearned\b",
            r"\bgrowth\b",
        ),
    ),
    (
        "concrete_impact",
        (
            r"\d+\s*%",
            r"\d+\s+человек",
            r"\d+\s+участник",
            r"\bimpact\b",
            r"\bresults?\b",
        ),
    ),
    (
        "mission_social",
        (
            r"\bмиссия",
            r"\bсоциальн",
            r"\bобществ",
            r"\bvolunteer",
            r"\bcommunity\b",
            r"\bsocial\b",
        ),
    ),
)


def rule_based_tags(normalized_lower_text: str) -> list[str]:
    t = (normalized_lower_text or "").lower()
    out: list[str] = []
    for tag, patterns in _TAG_RULES:
        for p in patterns:
            if re.search(p, t, flags=re.IGNORECASE):
                if tag not in out:
                    out.append(tag)
                break
    return out[:20]
