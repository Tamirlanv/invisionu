"""Behavioral personality/leadership profile from internal test answers.

Important: This is NOT a clinical psychological test and must not be used as a sole decision factor.
It produces an explainable multi-scale profile for human-in-the-loop review.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import InternalTestAnswer, InternalTestQuestion

TraitKey = Literal["INI", "RES", "COL", "ADP", "REF"]
AnswerKey = Literal["A", "B", "C", "D"]
Lang = Literal["ru", "en"]


class _QuestionCfg(TypedDict):
    id: str
    index: int
    scoring: dict[AnswerKey, dict[TraitKey, int]]


def _question_ids() -> list[str]:
    return [f"00000000-0000-4000-8000-{i:012d}" for i in range(1, 41)]


def _scoring_config() -> dict[str, dict[AnswerKey, dict[TraitKey, int]]]:
    """Map questionId -> scoring per answer. Mirrors web config exactly."""
    ids = _question_ids()
    # Q1..Q40 scoring map from the spec
    maps: list[dict[AnswerKey, dict[TraitKey, int]]] = [
        {"A": {"REF": 2, "RES": 1}, "B": {"INI": 2, "ADP": 1}, "C": {"COL": 2, "REF": 1}, "D": {"ADP": 2, "REF": 1}},
        {"A": {"COL": 2, "REF": 1}, "B": {"INI": 2, "ADP": 1}, "C": {"COL": 2, "RES": 1}, "D": {"ADP": 2, "INI": 1}},
        {"A": {"RES": 2, "REF": 1}, "B": {"INI": 2, "ADP": 1}, "C": {"COL": 2, "REF": 1}, "D": {"REF": 2, "ADP": 1}},
        {"A": {"REF": 2, "RES": 1}, "B": {"COL": 2, "INI": 1}, "C": {"INI": 2, "ADP": 1}, "D": {"ADP": 2, "REF": 1}},
        {"A": {"INI": 2, "ADP": 1}, "B": {"RES": 2, "REF": 1}, "C": {"COL": 2, "RES": 1}, "D": {"REF": 2, "ADP": 1}},
        {"A": {"RES": 2, "REF": 1}, "B": {"ADP": 2, "REF": 1}, "C": {"COL": 2, "ADP": 1}, "D": {"ADP": 2, "RES": 1}},
        {"A": {"COL": 2, "INI": 1}, "B": {"REF": 2, "COL": 1}, "C": {"COL": 2, "ADP": 1}, "D": {"REF": 2, "ADP": 1}},
        {"A": {"RES": 2, "ADP": 1}, "B": {"INI": 2, "RES": 1}, "C": {"ADP": 2, "RES": 1}, "D": {"COL": 2, "RES": 1}},
        {"A": {"REF": 2, "RES": 1}, "B": {"INI": 2, "RES": 1}, "C": {"COL": 2, "REF": 1}, "D": {"ADP": 2, "REF": 1}},
        {"A": {"REF": 2, "RES": 1}, "B": {"ADP": 2, "INI": 1}, "C": {"COL": 2, "REF": 1}, "D": {"RES": 2, "REF": 1}},
        {"A": {"INI": 2, "RES": 1}, "B": {"COL": 2, "REF": 1}, "C": {"REF": 2, "RES": 1}, "D": {"ADP": 2, "REF": 1}},
        {"A": {"RES": 2, "COL": 1}, "B": {"INI": 2, "ADP": 1}, "C": {"COL": 2, "REF": 1}, "D": {"REF": 2, "RES": 1}},
        {"A": {"REF": 2, "COL": 1}, "B": {"REF": 2, "ADP": 1}, "C": {"INI": 2, "RES": 1}, "D": {"COL": 2, "ADP": 1}},
        {"A": {"COL": 2, "INI": 1}, "B": {"REF": 2, "ADP": 1}, "C": {"COL": 2, "REF": 1}, "D": {"REF": 2, "COL": 1}},
        {"A": {"INI": 2, "ADP": 1}, "B": {"RES": 2, "REF": 1}, "C": {"COL": 2, "ADP": 1}, "D": {"ADP": 2, "REF": 1}},
        {"A": {"REF": 2, "RES": 1}, "B": {"REF": 2, "ADP": 1}, "C": {"COL": 2, "REF": 1}, "D": {"ADP": 2, "RES": 1}},
        {"A": {"COL": 2, "ADP": 1}, "B": {"RES": 2, "REF": 1}, "C": {"REF": 2, "COL": 1}, "D": {"ADP": 2, "REF": 1}},
        {"A": {"INI": 2, "COL": 1}, "B": {"RES": 2, "INI": 1}, "C": {"REF": 2, "COL": 1}, "D": {"REF": 2, "RES": 1}},
        {"A": {"RES": 2, "INI": 1}, "B": {"REF": 2, "ADP": 1}, "C": {"COL": 2, "REF": 1}, "D": {"ADP": 2, "REF": 1}},
        {"A": {"COL": 2, "RES": 1}, "B": {"RES": 2, "COL": 1}, "C": {"REF": 2, "COL": 1}, "D": {"COL": 2, "ADP": 1}},
        {"A": {"INI": 2, "RES": 1}, "B": {"RES": 2, "REF": 1}, "C": {"COL": 2, "REF": 1}, "D": {"ADP": 2, "REF": 1}},
        {"A": {"REF": 2, "RES": 1}, "B": {"ADP": 2, "INI": 1}, "C": {"COL": 2, "REF": 1}, "D": {"ADP": 2, "RES": 1}},
        {"A": {"REF": 2, "RES": 1}, "B": {"REF": 2, "ADP": 1}, "C": {"INI": 2, "RES": 1}, "D": {"COL": 2, "REF": 1}},
        {"A": {"RES": 2, "ADP": 1}, "B": {"REF": 2, "RES": 1}, "C": {"COL": 2, "RES": 1}, "D": {"ADP": 2, "RES": 1}},
        {"A": {"ADP": 2, "INI": 1}, "B": {"REF": 2, "RES": 1}, "C": {"COL": 2, "REF": 1}, "D": {"COL": 2, "ADP": 1}},
        {"A": {"INI": 2, "ADP": 1}, "B": {"RES": 2, "REF": 1}, "C": {"REF": 2, "RES": 1}, "D": {"ADP": 2, "INI": 1}},
        {"A": {"COL": 2, "REF": 1}, "B": {"COL": 2, "RES": 1}, "C": {"REF": 2, "COL": 1}, "D": {"ADP": 2, "COL": 1}},
        {"A": {"RES": 2, "REF": 1}, "B": {"INI": 2, "ADP": 1}, "C": {"COL": 2, "RES": 1}, "D": {"COL": 2, "REF": 1}},
        {"A": {"INI": 2, "RES": 1}, "B": {"ADP": 2, "INI": 1}, "C": {"REF": 2, "COL": 1}, "D": {"COL": 2, "REF": 1}},
        {"A": {"RES": 2, "REF": 1}, "B": {"INI": 2, "ADP": 1}, "C": {"ADP": 2, "RES": 1}, "D": {"REF": 2, "ADP": 1}},
        {"A": {"RES": 2, "REF": 1}, "B": {"ADP": 2, "INI": 1}, "C": {"COL": 2, "ADP": 1}, "D": {"ADP": 2, "REF": 1}},
        {"A": {"RES": 2, "COL": 1}, "B": {"INI": 2, "COL": 1}, "C": {"COL": 2, "REF": 1}, "D": {"REF": 2, "RES": 1}},
        {"A": {"REF": 2, "COL": 1}, "B": {"INI": 2, "COL": 1}, "C": {"RES": 2, "REF": 1}, "D": {"COL": 2, "RES": 1}},
        {"A": {"REF": 2, "COL": 1}, "B": {"RES": 2, "COL": 1}, "C": {"RES": 2, "ADP": 1}, "D": {"ADP": 2, "RES": 1}},
        {"A": {"INI": 2, "ADP": 1}, "B": {"RES": 2, "ADP": 1}, "C": {"REF": 2, "RES": 1}, "D": {"RES": 2, "COL": 1}},
        {"A": {"REF": 2, "RES": 1}, "B": {"RES": 2, "ADP": 1}, "C": {"ADP": 2, "REF": 1}, "D": {"ADP": 2, "REF": 1}},
        {"A": {"REF": 2, "RES": 1}, "B": {"INI": 2, "ADP": 1}, "C": {"COL": 2, "RES": 1}, "D": {"REF": 2, "ADP": 1}},
        {"A": {"RES": 2, "COL": 1}, "B": {"INI": 2, "COL": 1}, "C": {"RES": 2, "INI": 1}, "D": {"COL": 2, "ADP": 1}},
        {"A": {"RES": 2, "REF": 1}, "B": {"REF": 2, "ADP": 1}, "C": {"REF": 2, "COL": 1}, "D": {"ADP": 2, "RES": 1}},
        {"A": {"RES": 2, "INI": 1}, "B": {"COL": 2, "REF": 1}, "C": {"INI": 2, "ADP": 1}, "D": {"REF": 2, "RES": 1}},
    ]
    return {ids[i]: maps[i] for i in range(40)}


def _profile_texts(lang: Lang) -> dict[str, dict[str, Any]]:
    # Minimal localized texts for committee snapshot
    return {
        "INITIATOR": {
            "title": {"ru": "Инициатор", "en": "Initiator"}[lang],
            "summary": {
                "ru": "Склонен быстро переходить к действию и запускать движение.",
                "en": "Tends to move into action quickly and initiate momentum.",
            }[lang],
        },
        "ARCHITECT": {
            "title": {"ru": "Архитектор", "en": "Architect"}[lang],
            "summary": {
                "ru": "Силен в структуре, ответственности и последовательности.",
                "en": "Strong in structure, responsibility, and follow-through.",
            }[lang],
        },
        "INTEGRATOR": {
            "title": {"ru": "Интегратор", "en": "Integrator"}[lang],
            "summary": {
                "ru": "Силен в командном взаимодействии и объединении позиций.",
                "en": "Strong in collaboration and alignment of viewpoints.",
            }[lang],
        },
        "ADAPTER": {
            "title": {"ru": "Адаптер", "en": "Adapter"}[lang],
            "summary": {
                "ru": "Устойчив к неопределенности и быстро перестраивается.",
                "en": "Comfortable with uncertainty and adapts quickly.",
            }[lang],
        },
        "ANALYST": {
            "title": {"ru": "Аналитик", "en": "Analyst"}[lang],
            "summary": {
                "ru": "Склонен к осмыслению, анализу и вниманию к нюансам.",
                "en": "Leans toward reflection, analysis, and nuance.",
            }[lang],
        },
        "BALANCED": {
            "title": {"ru": "Сбалансированный профиль", "en": "Balanced profile"}[lang],
            "summary": {
                "ru": "Нет одного жестко доминирующего стиля; гибко переключается.",
                "en": "No single dominant style; switches flexibly across contexts.",
            }[lang],
        },
    }


def _rank(scores: dict[TraitKey, int]) -> list[tuple[TraitKey, int]]:
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def _percentages(scores: dict[TraitKey, int]) -> dict[TraitKey, float]:
    total = sum(scores.values())
    if not total:
        return {k: 0.0 for k in scores}
    return {k: (v / total) * 100.0 for k, v in scores.items()}


def _detect_profile_type(dominant: TraitKey, secondary: TraitKey, is_balanced: bool) -> str:
    if is_balanced:
        return "BALANCED"
    if dominant == "INI" and secondary in ("ADP", "RES"):
        return "INITIATOR"
    if dominant == "RES" and secondary in ("REF", "INI"):
        return "ARCHITECT"
    if dominant == "COL" and secondary in ("REF", "RES"):
        return "INTEGRATOR"
    if dominant == "ADP" and secondary in ("INI", "REF"):
        return "ADAPTER"
    if dominant == "REF" and secondary in ("RES", "COL"):
        return "ANALYST"
    return {"INI": "INITIATOR", "RES": "ARCHITECT", "COL": "INTEGRATOR", "ADP": "ADAPTER", "REF": "ANALYST"}[dominant]


def build_personality_profile_snapshot(
    db: Session,
    *,
    application_id: UUID,
    lang: Lang = "ru",
    include_non_finalized: bool = False,
) -> dict[str, Any]:
    """Build explainable profile for committee-side snapshot."""
    scoring = _scoring_config()
    desired_ids = set(_question_ids())

    stmt = select(InternalTestAnswer).where(InternalTestAnswer.application_id == application_id)
    if not include_non_finalized:
        stmt = stmt.where(InternalTestAnswer.is_finalized.is_(True))
    answers = list(db.scalars(stmt).all())

    scores: dict[TraitKey, int] = {"INI": 0, "RES": 0, "COL": 0, "ADP": 0, "REF": 0}
    contrib: list[dict[str, Any]] = []
    answer_keys: list[str] = []
    for a in answers:
        qid = str(a.question_id)
        if qid not in desired_ids:
            continue
        sel = (a.selected_options or [])
        if not sel:
            continue
        key = str(sel[0]).upper()
        if key not in ("A", "B", "C", "D"):
            continue
        rule = scoring.get(qid, {}).get(key) or {}
        for t, delta in rule.items():
            scores[t] += int(delta)
        contrib.append({"questionId": qid, "answer": key, "addedTo": rule})
        answer_keys.append(key)

    total = sum(scores.values())
    ranking = _rank(scores)
    dominant = ranking[0][0] if ranking else "INI"
    secondary = ranking[1][0] if len(ranking) > 1 else "RES"
    weakest = ranking[-1][0] if ranking else "REF"

    top1 = ranking[0][1] if ranking else 0
    top2 = ranking[1][1] if len(ranking) > 1 else 0
    top3 = ranking[2][1] if len(ranking) > 2 else 0
    is_balanced = abs(top1 - top3) <= 3
    has_strong = (top1 - top2) >= 5

    uniq = set(answer_keys)
    should_review = bool(is_balanced and (len(uniq) <= 2) and len(answer_keys) >= 30 and not has_strong)
    consistency_warning = bool((not has_strong) and (len(uniq) == 4) and len(answer_keys) >= 30)

    ptype = _detect_profile_type(dominant, secondary, is_balanced)
    texts = _profile_texts(lang)[ptype]

    trait_labels = {
        "INI": {"ru": "Инициативность", "en": "Initiative"},
        "RES": {"ru": "Ответственность", "en": "Reliability"},
        "COL": {"ru": "Командность", "en": "Collaboration"},
        "ADP": {"ru": "Адаптивность", "en": "Adaptability"},
        "REF": {"ru": "Рефлексивность", "en": "Reflectiveness"},
    }

    return {
        "rawScores": scores,
        "totalScore": total,
        "percentages": _percentages(scores),
        "ranking": [{"trait": t, "score": s} for t, s in ranking],
        "dominantTrait": dominant,
        "secondaryTrait": secondary,
        "weakestTrait": weakest,
        "profileType": ptype,
        "profileTitle": texts["title"],
        "summary": texts["summary"],
        "explainability": {
            "topTraitsWhy": [
                (
                    f"Высокий вклад в «{trait_labels[dominant][lang]}» сформировался за счёт выбранных вариантов, отражающих этот стиль поведения."
                    if lang == "ru"
                    else f'A higher score in \"{trait_labels[dominant][lang]}\" emerged from choices reflecting this behavioral style.'
                ),
                (
                    f"Вторая ведущая шкала — «{trait_labels[secondary][lang]}»: её усиливали ответы, где вы предпочитали соответствующий способ действовать."
                    if lang == "ru"
                    else f'The second leading dimension is \"{trait_labels[secondary][lang]}\", strengthened by answers favoring this way of acting.'
                ),
            ],
            "answerContributions": contrib,
            "lessExpressed": (
                f"Менее выраженная зона — «{trait_labels[weakest][lang]}»: она встречалась реже в выбранных вариантах."
                if lang == "ru"
                else f'A less expressed area is \"{trait_labels[weakest][lang]}\": it appeared less often in the selected options.'
            ),
        },
        "flags": {
            "isBalancedProfile": is_balanced,
            "hasStrongDominance": has_strong,
            "shouldReviewForSocialDesirability": should_review,
            "consistencyWarning": consistency_warning,
        },
        "meta": {
            "answerCount": len(contrib),
            "expectedQuestionCount": 40,
            "note": "Non-clinical behavioral questionnaire; human-in-the-loop only.",
        },
    }

