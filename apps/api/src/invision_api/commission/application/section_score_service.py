"""Section review scores — recommended score computation and CRUD.

Each tab has 3 score parameters rated 1-5. The platform computes recommended
values from processed signals; reviewers can override with manual scores.
"""

from __future__ import annotations

import math
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import TextAnalysisRun
from invision_api.models.commission import SectionReviewScore
from invision_api.models.data_check_unit_result import DataCheckUnitResult
from invision_api.models.enums import DataCheckUnitType
from invision_api.repositories import data_check_repository
from invision_api.services.data_check.status_service import TERMINAL_UNIT_STATUSES


_ScoreConfig = list[dict[str, str]]

SECTION_SCORE_CONFIGS: dict[str, _ScoreConfig] = {
    "personal": [
        {"key": "data_completeness", "label": "Полнота данных"},
        {"key": "document_correctness", "label": "Корректность документов"},
        {"key": "review_readiness", "label": "Готовность к review"},
    ],
    "test": [
        {"key": "leadership_potential", "label": "Лидерский потенциал"},
        {"key": "profile_stability", "label": "Устойчивость профиля"},
        {"key": "team_interaction", "label": "Командное взаимодействие"},
    ],
    "motivation": [
        {"key": "motivation_level", "label": "Мотивированность"},
        {"key": "choice_awareness", "label": "Осознанность выбора"},
        {"key": "specificity", "label": "Конкретика"},
    ],
    "path": [
        {"key": "initiative", "label": "Инициативность"},
        {"key": "resilience", "label": "Устойчивость"},
        {"key": "reflection_growth", "label": "Рефлексия и рост"},
    ],
    "achievements": [
        {"key": "achievement_level", "label": "Уровень достижений"},
        {"key": "personal_contribution", "label": "Личный вклад"},
        {"key": "confirmability", "label": "Подтверждённость"},
    ],
}


def _clamp(val: float, lo: int = 1, hi: int = 5) -> int:
    return max(lo, min(hi, round(val)))


def _scale_01_to_15(val: float | None) -> int:
    if val is None:
        return 3
    return _clamp(val * 5)


def _get_analysis_run(db: Session, application_id: UUID, block_key: str) -> TextAnalysisRun | None:
    return db.scalars(
        select(TextAnalysisRun)
        .where(TextAnalysisRun.application_id == application_id, TextAnalysisRun.block_key == block_key)
        .order_by(TextAnalysisRun.created_at.desc())
    ).first()


def _compute_personal_scores(db: Session, application_id: UUID) -> dict[str, int]:
    from invision_api.repositories import admissions_repository

    scores: dict[str, int] = {}

    app = admissions_repository.get_application_by_id(db, application_id)
    if app:
        section_states = {ss.section_key: ss for ss in (app.section_states or [])}
        required = ["personal", "contact", "education"]
        filled = sum(1 for s in required if s in section_states and section_states[s].is_complete)
        scores["data_completeness"] = _clamp(math.ceil(filled / len(required) * 5))
    else:
        scores["data_completeness"] = 1

    runs = data_check_repository.list_runs_for_application(db, application_id)
    unit_map: dict[str, DataCheckUnitResult] = {}
    if runs:
        for r in data_check_repository.list_unit_results_for_run(db, runs[0].id):
            unit_map[r.unit_type] = r

    doc_units = [
        unit_map.get(DataCheckUnitType.certificate_validation.value),
    ]
    doc_ok = sum(1 for u in doc_units if u and u.status == "completed")
    doc_total = sum(1 for u in doc_units if u)
    if doc_total > 0:
        scores["document_correctness"] = _clamp(math.ceil(doc_ok / doc_total * 5))
    else:
        scores["document_correctness"] = 3

    terminal = sum(1 for u in unit_map.values() if u.status in TERMINAL_UNIT_STATUSES)
    total = len(unit_map) if unit_map else 1
    manual_needed = sum(1 for u in unit_map.values() if u.manual_review_required)
    if terminal == total and manual_needed == 0:
        scores["review_readiness"] = 5
    elif terminal == total:
        scores["review_readiness"] = 3
    else:
        scores["review_readiness"] = _clamp(math.ceil(terminal / total * 4))

    return scores


def _compute_test_scores(db: Session, application_id: UUID) -> dict[str, int]:
    scores: dict[str, int] = {}
    run = _get_analysis_run(db, application_id, "test_profile")
    profile = ((run.explanations or {}).get("profile", {})) if run else {}
    ranking = profile.get("ranking", [])
    flags = profile.get("flags", {})
    meta = profile.get("meta", {})

    ini_score = 3
    for entry in ranking:
        if entry.get("trait") == "INI":
            raw = entry.get("score", 0)
            total = sum(e.get("score", 0) for e in ranking) or 1
            ini_score = _clamp(math.ceil(raw / total * 5 * len(ranking)))
            break
    scores["leadership_potential"] = ini_score

    answer_count = meta.get("answerCount", 0)
    expected = meta.get("expectedQuestionCount", 40)
    consistency_ok = not flags.get("consistencyWarning", False)
    social_ok = not flags.get("shouldReviewForSocialDesirability", False)
    stability = 5
    if answer_count < expected:
        stability -= 1
    if not consistency_ok:
        stability -= 1
    if not social_ok:
        stability -= 1
    scores["profile_stability"] = _clamp(stability)

    col_score = 3
    for entry in ranking:
        if entry.get("trait") == "COL":
            raw = entry.get("score", 0)
            total = sum(e.get("score", 0) for e in ranking) or 1
            col_score = _clamp(math.ceil(raw / total * 5 * len(ranking)))
            break
    scores["team_interaction"] = col_score

    return scores


def _compute_motivation_scores(db: Session, application_id: UUID) -> dict[str, int]:
    scores: dict[str, int] = {}
    run = _get_analysis_run(db, application_id, "motivation_goals")
    signals = ((run.explanations or {}).get("signals", {})) if run else {}

    mot_density = signals.get("motivation_density")
    if mot_density is not None:
        if mot_density > 0.2:
            scores["motivation_level"] = 5
        elif mot_density > 0.15:
            scores["motivation_level"] = 4
        elif mot_density > 0.08:
            scores["motivation_level"] = 3
        elif mot_density > 0.03:
            scores["motivation_level"] = 2
        else:
            scores["motivation_level"] = 1
    else:
        scores["motivation_level"] = 3

    word_count = signals.get("word_count", 0)
    if word_count >= 200:
        scores["choice_awareness"] = 5
    elif word_count >= 120:
        scores["choice_awareness"] = 4
    elif word_count >= 70:
        scores["choice_awareness"] = 3
    elif word_count >= 30:
        scores["choice_awareness"] = 2
    else:
        scores["choice_awareness"] = 1

    evidence = signals.get("evidence_density")
    if evidence is not None:
        if evidence > 0.15:
            scores["specificity"] = 5
        elif evidence > 0.10:
            scores["specificity"] = 4
        elif evidence > 0.05:
            scores["specificity"] = 3
        elif evidence > 0.02:
            scores["specificity"] = 2
        else:
            scores["specificity"] = 1
    else:
        scores["specificity"] = 3

    return scores


def _compute_path_scores(db: Session, application_id: UUID) -> dict[str, int]:
    scores: dict[str, int] = {}
    run = _get_analysis_run(db, application_id, "growth_journey")
    section_signals = ((run.explanations or {}).get("section_signals", {})) if run else {}

    scores["initiative"] = _scale_01_to_15(section_signals.get("initiative_score"))
    scores["resilience"] = _scale_01_to_15(section_signals.get("resilience_score"))
    scores["reflection_growth"] = _scale_01_to_15(section_signals.get("growth_score"))

    return scores


def _compute_achievements_scores(db: Session, application_id: UUID) -> dict[str, int]:
    scores: dict[str, int] = {}
    run = _get_analysis_run(db, application_id, "achievements_activities")
    signals = ((run.explanations or {}).get("signals", {})) if run else {}

    impact = signals.get("impact_markers", 0)
    word_count = signals.get("word_count", 0)
    if impact >= 3 and word_count >= 100:
        scores["achievement_level"] = 5
    elif impact >= 2 or word_count >= 80:
        scores["achievement_level"] = 4
    elif impact >= 1 or word_count >= 50:
        scores["achievement_level"] = 3
    elif word_count >= 20:
        scores["achievement_level"] = 2
    else:
        scores["achievement_level"] = 1

    has_role = signals.get("has_role", False)
    has_year = signals.get("has_year", False)
    contribution = 3
    if has_role:
        contribution += 1
    if has_year:
        contribution += 1
    if not has_role and impact == 0:
        contribution = 1
    scores["personal_contribution"] = _clamp(contribution)

    links_count = signals.get("links_count", 0)
    runs = data_check_repository.list_runs_for_application(db, application_id)
    link_reachable = 0
    link_total = 0
    if runs:
        for r in data_check_repository.list_unit_results_for_run(db, runs[0].id):
            if r.unit_type == DataCheckUnitType.link_validation.value:
                payload = r.result_payload or {}
                checked = payload.get("links", [])
                link_total = len(checked)
                link_reachable = sum(1 for ln in checked if ln.get("isReachable"))

    if links_count >= 2 and link_reachable == link_total and link_total > 0:
        scores["confirmability"] = 5
    elif links_count >= 1 and link_reachable > 0:
        scores["confirmability"] = 4
    elif links_count >= 1:
        scores["confirmability"] = 3
    elif has_year:
        scores["confirmability"] = 2
    else:
        scores["confirmability"] = 1

    return scores


_COMPUTE_MAP = {
    "personal": _compute_personal_scores,
    "test": _compute_test_scores,
    "motivation": _compute_motivation_scores,
    "path": _compute_path_scores,
    "achievements": _compute_achievements_scores,
}


def compute_recommended_scores(db: Session, application_id: UUID, section: str) -> dict[str, int]:
    fn = _COMPUTE_MAP.get(section)
    if not fn:
        return {}
    return fn(db, application_id)


def get_section_scores(
    db: Session,
    *,
    application_id: UUID,
    section: str,
    reviewer_user_id: UUID,
) -> dict[str, Any]:
    config = SECTION_SCORE_CONFIGS.get(section)
    if not config:
        return {"section": section, "items": [], "totalScore": 0, "maxTotalScore": 0}

    recommended = compute_recommended_scores(db, application_id, section)

    saved_rows = db.scalars(
        select(SectionReviewScore).where(
            SectionReviewScore.application_id == application_id,
            SectionReviewScore.reviewer_user_id == reviewer_user_id,
            SectionReviewScore.section == section,
        )
    ).all()
    saved_map = {r.score_key: r for r in saved_rows}

    items: list[dict[str, Any]] = []
    total = 0
    for cfg in config:
        key = cfg["key"]
        rec = recommended.get(key, 3)
        saved = saved_map.get(key)
        manual = saved.manual_score if saved else None
        effective = manual if manual is not None else rec
        items.append({
            "key": key,
            "label": cfg["label"],
            "recommendedScore": rec,
            "manualScore": manual,
            "effectiveScore": effective,
        })
        total += effective

    return {
        "section": section,
        "items": items,
        "totalScore": total,
        "maxTotalScore": len(config) * 5,
    }


def save_section_scores(
    db: Session,
    *,
    application_id: UUID,
    section: str,
    reviewer_user_id: UUID,
    scores: list[dict[str, int]],
) -> dict[str, Any]:
    config = SECTION_SCORE_CONFIGS.get(section)
    if not config:
        return {"ok": False}

    valid_keys = {c["key"] for c in config}
    recommended = compute_recommended_scores(db, application_id, section)

    for item in scores:
        key = item.get("key", "")
        score_val = item.get("score")
        if key not in valid_keys or not isinstance(score_val, int) or not (1 <= score_val <= 5):
            continue

        row = db.scalars(
            select(SectionReviewScore).where(
                SectionReviewScore.application_id == application_id,
                SectionReviewScore.reviewer_user_id == reviewer_user_id,
                SectionReviewScore.section == section,
                SectionReviewScore.score_key == key,
            )
        ).first()

        rec = recommended.get(key, 3)
        if row:
            row.manual_score = score_val
            row.recommended_score = rec
        else:
            row = SectionReviewScore(
                application_id=application_id,
                reviewer_user_id=reviewer_user_id,
                section=section,
                score_key=key,
                recommended_score=rec,
                manual_score=score_val,
            )
            db.add(row)

    db.flush()
    return get_section_scores(
        db,
        application_id=application_id,
        section=section,
        reviewer_user_id=reviewer_user_id,
    )
