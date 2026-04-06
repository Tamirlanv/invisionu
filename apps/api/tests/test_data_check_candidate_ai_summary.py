from __future__ import annotations

from sqlalchemy.orm import Session

from invision_api.models.application import AIReviewMetadata
from invision_api.repositories import data_check_repository
from invision_api.services.data_check.processors.candidate_ai_summary_processor import (
    run_candidate_ai_summary_processing,
)


def test_data_check_candidate_ai_summary_uses_llm_when_available(
    db: Session, factory, monkeypatch
):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    run = data_check_repository.create_run(
        db,
        candidate_id=profile.id,
        application_id=app.id,
        status="running",
    )
    data_check_repository.upsert_candidate_signals_aggregate(
        db,
        run_id=run.id,
        application_id=app.id,
        leadership_signals={"score": 1.0},
        initiative_signals={"score": 1.0},
        resilience_signals={"score": 1.0},
        responsibility_signals={"score": 1.0},
        growth_signals={"score": 1.0},
        mission_fit_signals={"score": 1.0},
        strong_motivation_signals={"score": 1.0},
        communication_signals={"score": 1.0},
        attention_flags=[],
        authenticity_concern_signals=[],
        review_readiness_status="ready_for_commission",
        manual_review_required=False,
        explainability=[],
    )

    monkeypatch.setattr(
        "invision_api.services.data_check.llm.llm_summary_client.INTERNAL_LLM_SUMMARY_URL",
        "http://llm.local/summary",
    )

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            _ = (args, kwargs)

        @property
        def enabled(self) -> bool:
            return True

        def summarize(self, *, payload):
            _ = payload
            return {"summary": "LLM summary text", "key_points": ["a", "b"], "provider": "internal_llm"}

    monkeypatch.setattr(
        "invision_api.services.data_check.processors.candidate_ai_summary_processor.LLMSummaryClient",
        _FakeClient,
    )

    out = run_candidate_ai_summary_processing(db, application_id=app.id, run_id=run.id)
    db.flush()

    assert out.status == "completed"
    assert out.payload is not None
    assert out.payload["summary"] == "LLM summary text"

    ai_rows = list(db.query(AIReviewMetadata).filter(AIReviewMetadata.application_id == app.id).all())
    assert len(ai_rows) == 1
    assert ai_rows[0].summary_text == "LLM summary text"


def test_data_check_candidate_ai_summary_degraded_fallback_without_aggregate(
    db: Session, factory
) -> None:
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    run = data_check_repository.create_run(
        db,
        candidate_id=profile.id,
        application_id=app.id,
        status="running",
    )
    data_check_repository.upsert_unit_result(
        db,
        run_id=run.id,
        application_id=app.id,
        unit_type="test_profile_processing",
        status="completed",
        result_payload={"profile": {"dominantTrait": "INI"}},
        warnings=[],
        errors=[],
        explainability=[],
        manual_review_required=False,
        attempts=1,
        started_at=None,
        finished_at=None,
    )

    out = run_candidate_ai_summary_processing(db, application_id=app.id, run_id=run.id)
    db.flush()

    assert out.status == "manual_review_required"
    assert out.payload is not None
    assert "ограниченном режиме" in out.payload["summary"].lower()

    ai_rows = list(db.query(AIReviewMetadata).filter(AIReviewMetadata.application_id == app.id).all())
    assert len(ai_rows) == 1
    assert ai_rows[0].prompt_version == "data_check_v1_degraded"
