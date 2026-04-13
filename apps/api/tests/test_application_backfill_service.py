from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import AIReviewMetadata
from invision_api.models.commission import ReviewRubricScore
from invision_api.models.candidate_validation_orchestration import CandidateValidationRun
from invision_api.models.enums import ApplicationStage, DataCheckRunStatus
from invision_api.repositories import admissions_repository
from invision_api.repositories import data_check_repository
from invision_api.services.backfill import application_backfill_service as svc
from invision_api.services.data_check.contracts import UnitExecutionResult


def _make_submitted_application(db: Session, factory, *, stage: str = ApplicationStage.initial_screening.value):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = stage
    app.submitted_at = datetime.now(tz=UTC)
    app.locked_after_submit = True
    db.flush()
    return app, user


def test_backfill_analysis_only_dry_run_has_no_writes(db: Session, factory) -> None:
    app, _ = _make_submitted_application(db, factory, stage=ApplicationStage.application_review.value)

    result = svc.reprocess_application(
        db,
        application_id=app.id,
        options=svc.BackfillOptions(
            mode="analysis_only",
            dry_run=True,
            application_ids=(app.id,),
        ),
    )

    assert result.status == "dry_run"
    assert "refresh_review_snapshot" in result.actions
    assert admissions_repository.get_review_snapshot(db, app.id) is None
    ai_rows = list(db.scalars(select(AIReviewMetadata).where(AIReviewMetadata.application_id == app.id)).all())
    assert ai_rows == []


def test_backfill_analysis_only_is_stage_aware_for_ai_interview_calls(db: Session, factory, monkeypatch) -> None:
    app, _ = _make_submitted_application(db, factory, stage=ApplicationStage.initial_screening.value)

    called: dict[str, int] = {"draft": 0, "resolution": 0}

    def _fake_snapshot(_db, _application_id, *, review_status):
        _ = review_status
        return None

    def _fake_ai_pipeline(_db, *, application_id, actor_user_id, force=False):
        _ = (application_id, actor_user_id, force)
        return None

    def _fake_draft(*args, **kwargs):
        _ = (args, kwargs)
        called["draft"] += 1
        return None

    def _fake_resolution(*args, **kwargs):
        _ = (args, kwargs)
        called["resolution"] += 1
        return None

    monkeypatch.setattr(svc, "upsert_snapshot_from_packet", _fake_snapshot)
    monkeypatch.setattr(svc, "run_commission_ai_pipeline", _fake_ai_pipeline)
    monkeypatch.setattr(svc, "ensure_ai_interview_draft_best_effort", _fake_draft)
    monkeypatch.setattr(svc, "ensure_resolution_summary_available", _fake_resolution)

    result = svc.reprocess_application(
        db,
        application_id=app.id,
        options=svc.BackfillOptions(mode="analysis_only", dry_run=False, application_ids=(app.id,)),
    )

    assert result.status == "processed"
    assert called["draft"] == 0
    assert called["resolution"] == 0


def test_collect_target_application_ids_only_missing_filter(db: Session, factory) -> None:
    app_missing, _ = _make_submitted_application(db, factory)
    app_ready, _ = _make_submitted_application(db, factory)

    db.add(
        AIReviewMetadata(
            application_id=app_ready.id,
            model="test",
            prompt_version="v1",
            summary_text="Есть итоговая сводка",
            flags={"provider": "test"},
            explainability_snapshot=None,
            authenticity_risk_score=None,
            decision_authority="human_only",
        )
    )
    db.flush()

    ids = svc.collect_target_application_ids(
        db,
        svc.BackfillOptions(
            mode="analysis_only",
            only_missing=("commission_ai_summary",),
        ),
    )

    assert app_missing.id in ids
    assert app_ready.id not in ids


def test_backfill_full_executes_units_in_order_without_stage_transition(db: Session, factory, monkeypatch) -> None:
    app, _ = _make_submitted_application(db, factory, stage=ApplicationStage.initial_screening.value)
    initial_stage = app.current_stage

    order: list[str] = []

    def _make_processor(unit_name: str):
        def _processor(_db, application_id, candidate_id, run_id):
            _ = (application_id, candidate_id, run_id)
            order.append(unit_name)
            return UnitExecutionResult(status="completed", payload={"ok": True})

        return _processor

    for unit in svc.FULL_UNIT_ORDER:
        monkeypatch.setitem(svc.REGISTRY, unit, _make_processor(unit.value))

    monkeypatch.setattr(svc, "_run_analysis_only_actions", lambda *args, **kwargs: ["analysis_only_post_steps"])

    result = svc.reprocess_application(
        db,
        application_id=app.id,
        options=svc.BackfillOptions(
            mode="full",
            backfill_version="2026-04-test-v1",
            application_ids=(app.id,),
        ),
    )

    assert result.status == "processed"
    assert order == [u.value for u in svc.FULL_UNIT_ORDER]

    db.refresh(app)
    assert app.current_stage == initial_stage

    latest_run = db.scalars(
        select(CandidateValidationRun)
        .where(CandidateValidationRun.application_id == app.id)
        .order_by(CandidateValidationRun.created_at.desc())
    ).first()
    assert latest_run is not None
    assert latest_run.overall_status == DataCheckRunStatus.ready.value
    assert any(line == "backfill_version=2026-04-test-v1" for line in (latest_run.explainability or []))


def test_backfill_full_can_auto_advance_ready_from_initial_screening(db: Session, factory, monkeypatch) -> None:
    app, _ = _make_submitted_application(db, factory, stage=ApplicationStage.initial_screening.value)

    def _make_processor(_unit_name: str):
        def _processor(_db, application_id, candidate_id, run_id):
            _ = (application_id, candidate_id, run_id)
            return UnitExecutionResult(status="completed", payload={"ok": True})

        return _processor

    for unit in svc.FULL_UNIT_ORDER:
        monkeypatch.setitem(svc.REGISTRY, unit, _make_processor(unit.value))

    monkeypatch.setattr(svc, "_run_analysis_only_actions", lambda *args, **kwargs: ["analysis_only_post_steps"])

    result = svc.reprocess_application(
        db,
        application_id=app.id,
        options=svc.BackfillOptions(
            mode="full",
            backfill_version="2026-04-test-v2",
            auto_advance_ready=True,
            application_ids=(app.id,),
        ),
    )

    assert result.status == "processed"
    assert "auto_advance_ready_ok" in result.actions
    db.refresh(app)
    assert app.current_stage == ApplicationStage.application_review.value


def test_backfill_full_skips_same_version_without_force(db: Session, factory, monkeypatch) -> None:
    app, _ = _make_submitted_application(db, factory)

    data_check_repository.create_run(
        db,
        candidate_id=app.candidate_profile_id,
        application_id=app.id,
        status=DataCheckRunStatus.ready.value,
        explainability=["backfill_version=2026-04-prod-v1", "backfill_mode=full"],
    )
    db.flush()

    skipped = svc.reprocess_application(
        db,
        application_id=app.id,
        options=svc.BackfillOptions(
            mode="full",
            backfill_version="2026-04-prod-v1",
            application_ids=(app.id,),
        ),
    )
    assert skipped.status == "skipped"
    assert skipped.reason == "already_backfilled_for_version"

    called = {"full": 0}

    def _fake_full(*args, **kwargs):
        called["full"] += 1
        return uuid4(), []

    monkeypatch.setattr(svc, "_run_full_data_check_recompute", _fake_full)
    monkeypatch.setattr(svc, "_run_analysis_only_actions", lambda *args, **kwargs: [])

    forced = svc.reprocess_application(
        db,
        application_id=app.id,
        options=svc.BackfillOptions(
            mode="full",
            force=True,
            backfill_version="2026-04-prod-v1",
            application_ids=(app.id,),
        ),
    )

    assert forced.status == "processed"
    assert called["full"] == 1


def test_backfill_does_not_touch_manual_rubric_scores(db: Session, factory, monkeypatch) -> None:
    app, reviewer = _make_submitted_application(db, factory, stage=ApplicationStage.application_review.value)
    row = ReviewRubricScore(
        application_id=app.id,
        reviewer_user_id=reviewer.id,
        rubric="motivation",
        score="strong",
        comment="manual",
        revision=3,
    )
    db.add(row)
    db.flush()

    monkeypatch.setattr(svc, "upsert_snapshot_from_packet", lambda *args, **kwargs: None)
    monkeypatch.setattr(svc, "run_commission_ai_pipeline", lambda *args, **kwargs: None)
    monkeypatch.setattr(svc, "ensure_ai_interview_draft_best_effort", lambda *args, **kwargs: None)
    monkeypatch.setattr(svc, "rebuild_projection", lambda *args, **kwargs: None)

    result = svc.reprocess_application(
        db,
        application_id=app.id,
        options=svc.BackfillOptions(mode="analysis_only", application_ids=(app.id,)),
    )

    assert result.status == "processed"
    db.refresh(row)
    assert row.score == "strong"
    assert row.comment == "manual"
    assert row.revision == 3
