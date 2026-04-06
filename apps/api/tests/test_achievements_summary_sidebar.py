from __future__ import annotations

from datetime import UTC, datetime

from invision_api.commission.application.sidebar_service import _build_achievements_summary_panel
from invision_api.models.application import AIReviewMetadata
from invision_api.models.enums import DataCheckUnitStatus, DataCheckUnitType
from invision_api.repositories import data_check_repository


def test_achievements_sidebar_has_final_summary_and_archive_recommendation_by_default(db, factory) -> None:
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)

    db.add(
        AIReviewMetadata(
            application_id=app.id,
            model="test",
            prompt_version="v1",
            summary_text="Кандидат демонстрирует стабильную мотивацию и опыт командной работы.",
            flags={"strengths": ["устойчивая мотивация"], "weak_points": ["мало конкретики в достижениях"]},
            explainability_snapshot=None,
            authenticity_risk_score=None,
            decision_authority="human_only",
        )
    )
    db.flush()

    panel = _build_achievements_summary_panel(db, app.id)
    titles = [s["title"] for s in panel["sections"]]
    assert "Итоговая сводка" in titles
    assert "Рекомендация" in titles

    rec_section = next(s for s in panel["sections"] if s["title"] == "Рекомендация")
    rec_text = " ".join(str(x) for x in rec_section["items"]).lower()
    assert "средний рекомендованный балл" in rec_text
    assert "отправить в архив" in rec_text


def test_achievements_sidebar_prefers_candidate_summary_from_unit_payload(db, factory) -> None:
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)

    db.add(
        AIReviewMetadata(
            application_id=app.id,
            model="test",
            prompt_version="v1",
            summary_text="Старый fallback summary",
            flags={},
            explainability_snapshot=None,
            authenticity_risk_score=None,
            decision_authority="human_only",
        )
    )
    run = data_check_repository.create_run(
        db,
        candidate_id=profile.id,
        application_id=app.id,
        status="completed",
    )
    data_check_repository.upsert_unit_result(
        db,
        run_id=run.id,
        application_id=app.id,
        unit_type=DataCheckUnitType.candidate_ai_summary.value,
        status=DataCheckUnitStatus.completed.value,
        result_payload={"summary": "Новый итог из data-check pipeline по всей анкете."},
        warnings=[],
        errors=[],
        explainability=[],
        manual_review_required=False,
        attempts=1,
        started_at=datetime.now(tz=UTC),
        finished_at=datetime.now(tz=UTC),
    )

    panel = _build_achievements_summary_panel(db, app.id)
    summary_section = next(s for s in panel["sections"] if s["title"] == "Итоговая сводка")
    text = " ".join(str(x) for x in summary_section["items"]).lower()
    assert "новый итог" in text


def test_achievements_sidebar_recommends_interview_when_average_ge_3_5(db, factory, monkeypatch) -> None:
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)

    def _fake_recommended_scores(_db, _application_id, _section):
        return {"a": 4, "b": 4, "c": 4}

    monkeypatch.setattr(
        "invision_api.commission.application.section_score_service.compute_recommended_scores",
        _fake_recommended_scores,
    )

    panel = _build_achievements_summary_panel(db, app.id)
    rec_section = next(s for s in panel["sections"] if s["title"] == "Рекомендация")
    rec_text = " ".join(str(x) for x in rec_section["items"]).lower()
    assert "средний рекомендованный балл: 4.0" in rec_text
    assert "отправить на собеседование" in rec_text


def test_achievements_sidebar_ignores_generic_technical_summary_text(db, factory, monkeypatch) -> None:
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)

    db.add(
        AIReviewMetadata(
            application_id=app.id,
            model="test",
            prompt_version="v1",
            summary_text=(
                "Итоговая сводка сформирована автоматически. "
                "Текущий статус готовности: partial_processing_ready. "
                "Зоны внимания: candidate_ai_summary:manual_review."
            ),
            flags={},
            explainability_snapshot=None,
            authenticity_risk_score=None,
            decision_authority="human_only",
        )
    )

    def _fake_recommended_scores(_db, _application_id, _section):
        return {"a": 4, "b": 4, "c": 4}

    monkeypatch.setattr(
        "invision_api.commission.application.section_score_service.compute_recommended_scores",
        _fake_recommended_scores,
    )

    panel = _build_achievements_summary_panel(db, app.id)
    summary_section = next(s for s in panel["sections"] if s["title"] == "Итоговая сводка")
    text = " ".join(str(x) for x in summary_section["items"]).lower()
    assert "статус готовности" not in text
    assert "зоны внимания:" not in text
    assert "показывает сильный" in text
