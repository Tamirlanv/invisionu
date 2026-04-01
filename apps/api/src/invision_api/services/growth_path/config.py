"""Limits and tunable thresholds for growth path analysis."""

from typing import Final

# Per-question (min, max) character counts after normalization.
GROWTH_CHAR_LIMITS: Final[dict[str, tuple[int, int]]] = {
    "q1": (250, 700),
    "q2": (200, 700),
    "q3": (200, 700),
    "q4": (200, 700),
    "q5": (150, 700),
}

GROWTH_QUESTION_ORDER: Final[tuple[str, ...]] = ("q1", "q2", "q3", "q4", "q5")

# Low-effort: if unique token ratio below this, flag (Cyrillic/Latin word tokens).
UNIQUE_WORD_RATIO_LOW: Final[float] = 0.35

# Repetition: same sentence repeated many times.
MAX_REPEATED_SENTENCE_RATIO: Final[float] = 0.4

# Banned / spammy short phrases (case-insensitive substring after normalize).
SPAM_PHRASES: Final[tuple[str, ...]] = (
    "я понял",
    "lorem ipsum",
    "тест тест",
    "asdf",
    "qwerty",
    "заполните поле",
    "текст текст текст",
)
