"""Integration tests for the application submit flow."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import Application, ApplicationStageHistory, AnalysisJob
from invision_api.models.commission import ApplicationCommissionProjection
from invision_api.models.enums import ApplicationStage, ApplicationState, JobType, SectionKey
from invision_api.services.application_service import (
    REQUIRED_SECTIONS,
    SUBMIT_PIPELINE_CODE_WORKER,
    completion_percentage,
    reopen_application_for_resubmit,
    submit_application,
    submit_application_with_outcome,
)


class _FakeRedis:
    """Minimal Redis stub: heartbeat key always present."""
    def exists(self, *_args, **_kwargs) -> int:
        return 1
    def setex(self, *_args, **_kwargs) -> None:
        pass


def _mock_pipeline_ready(monkeypatch) -> None:
    monkeypatch.setattr("invision_api.services.application_service.redis_ping", lambda: True)
    monkeypatch.setattr(
        "invision_api.services.application_service.get_redis_client",
        lambda: _FakeRedis(),
    )
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_args, **_kwargs: None)


def test_submit_requires_verified_email(db: Session, factory):
    """Submit must reject users without verified email."""
    user = factory.user(db, verified=False)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    factory.fill_required_sections(db, app)
    db.commit()

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        submit_application(db, user)
    assert exc_info.value.status_code == 403


def test_submit_requires_all_sections_complete(db: Session, factory):
    """Submit with missing sections returns 400 with missing_sections list."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.commit()

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        submit_application(db, user)
    assert exc_info.value.status_code == 400
    assert "missing_sections" in str(exc_info.value.detail)


def test_submit_happy_path_sets_state_and_locks(db: Session, factory, monkeypatch):
    """Successful submit sets state to under_screening, locks editing, records stage history."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="in_progress")
    factory.fill_required_sections(db, app)
    db.commit()

    _mock_pipeline_ready(monkeypatch)

    # Mock the post-submit jobs to keep test scope narrow.
    import invision_api.services.stages.initial_screening_service as iss
    original = iss.enqueue_post_submit_jobs
    iss.enqueue_post_submit_jobs = lambda db, app_id, **_kwargs: None

    try:
        result = submit_application(db, user)
        assert result.locked_after_submit is True
        assert result.state == ApplicationState.under_screening.value
        assert result.current_stage == ApplicationStage.initial_screening.value
        assert result.submitted_at is not None

        histories = list(db.scalars(
            select(ApplicationStageHistory)
            .where(ApplicationStageHistory.application_id == app.id)
            .order_by(ApplicationStageHistory.entered_at.desc())
        ).all())
        assert len(histories) >= 2
        latest = histories[0]
        assert latest.to_stage == ApplicationStage.initial_screening.value
    finally:
        iss.enqueue_post_submit_jobs = original


def test_submit_duplicate_returns_409(db: Session, factory, monkeypatch):
    """Second submit on locked application returns 409."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="in_progress")
    factory.fill_required_sections(db, app)
    db.commit()

    _mock_pipeline_ready(monkeypatch)

    import invision_api.services.stages.initial_screening_service as iss
    original = iss.enqueue_post_submit_jobs
    iss.enqueue_post_submit_jobs = lambda db, app_id, **_kwargs: None

    try:
        submit_application(db, user)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            submit_application(db, user)
        assert exc_info.value.status_code == 409
    finally:
        iss.enqueue_post_submit_jobs = original


def test_submit_rejects_when_pipeline_not_ready(db: Session, factory, monkeypatch):
    """Submit must fail with 503 when readiness check says pipeline is unavailable."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="in_progress")
    factory.fill_required_sections(db, app)
    db.commit()
    app_id = app.id

    monkeypatch.setattr("invision_api.services.application_service.redis_ping", lambda: False)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        submit_application(db, user)
    assert exc_info.value.status_code == 503
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail.get("code") == "submit_pipeline_redis"
    assert "message" in detail

    db.expire_all()
    current = db.get(Application, app_id)
    assert current is not None
    assert current.state == ApplicationState.in_progress.value
    assert current.current_stage == ApplicationStage.application.value
    assert current.locked_after_submit is False
    assert current.submitted_at is None

    screening_job = db.scalars(
        select(AnalysisJob).where(
            AnalysisJob.application_id == app_id,
            AnalysisJob.job_type == JobType.initial_screening.value,
        )
    ).first()
    assert screening_job is None


def test_submit_503_when_worker_heartbeat_missing(db: Session, factory, monkeypatch):
    """503 with code submit_pipeline_worker when Redis is up but worker heartbeat key is absent."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="in_progress")
    factory.fill_required_sections(db, app)
    db.commit()

    class _RedisNoHeartbeat:
        def exists(self, *_args, **_kwargs) -> int:
            return 0

    monkeypatch.setattr("invision_api.services.application_service.redis_ping", lambda: True)
    monkeypatch.setattr(
        "invision_api.services.application_service.get_redis_client",
        lambda: _RedisNoHeartbeat(),
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        submit_application(db, user)
    assert exc_info.value.status_code == 503
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail.get("code") == SUBMIT_PIPELINE_CODE_WORKER


def test_submit_outcome_503_and_no_transition_when_enqueue_fails(db: Session, factory, monkeypatch):
    """Strict submit: enqueue failure returns 503 and leaves app in application stage."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="in_progress")
    factory.fill_required_sections(db, app)
    db.commit()
    app_id = app.id

    monkeypatch.setattr("invision_api.services.application_service.redis_ping", lambda: True)
    monkeypatch.setattr(
        "invision_api.services.application_service.get_redis_client",
        lambda: _FakeRedis(),
    )

    def _raise_redis(*_args, **_kwargs):
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", _raise_redis)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        submit_application_with_outcome(db, user)
    assert exc_info.value.status_code == 503
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail.get("code") == "submit_queue_enqueue"
    assert detail.get("enqueue_context")

    db.expire_all()
    current = db.get(Application, app_id)
    assert current is not None
    assert current.current_stage == ApplicationStage.application.value
    assert current.state == ApplicationState.in_progress.value
    assert current.locked_after_submit is False
    assert current.submitted_at is None

    projection = db.get(ApplicationCommissionProjection, app_id)
    assert projection is None

    failed_jobs = list(
        db.scalars(
            select(AnalysisJob).where(
                AnalysisJob.application_id == app_id,
            )
        ).all()
    )
    assert failed_jobs == []


def test_reopen_for_resubmit_returns_candidate_to_first_stage(db: Session, factory):
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.under_screening.value)
    now = datetime.now(tz=UTC) - timedelta(minutes=5)
    app.current_stage = ApplicationStage.initial_screening.value
    app.locked_after_submit = True
    app.submitted_at = now
    db.add(
        AnalysisJob(
            application_id=app.id,
            job_type=JobType.initial_screening.value,
            payload={},
            status="failed",
            attempts=1,
            last_error="queue_enqueue_failed: redis unavailable",
        )
    )
    db.commit()

    reopened = reopen_application_for_resubmit(db, user)
    assert reopened.current_stage == ApplicationStage.application.value
    assert reopened.state == ApplicationState.in_progress.value
    assert reopened.locked_after_submit is False
    assert reopened.submitted_at is None


def test_reopen_for_resubmit_rejected_without_queue_failure(db: Session, factory):
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state=ApplicationState.under_screening.value)
    app.current_stage = ApplicationStage.initial_screening.value
    app.locked_after_submit = True
    app.submitted_at = datetime.now(tz=UTC)
    db.commit()

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        reopen_application_for_resubmit(db, user)
    assert exc_info.value.status_code == 409


def test_completion_percentage_all_complete(db: Session, factory):
    """All required sections complete gives 100%."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    factory.fill_required_sections(db, app)
    db.flush()

    pct, missing = completion_percentage(db, app)
    assert pct == 100
    assert missing == []


def test_completion_percentage_missing_sections(db: Session, factory):
    """No sections filled gives 0%."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.flush()

    pct, missing = completion_percentage(db, app)
    assert pct == 0
    assert len(missing) == len(REQUIRED_SECTIONS)


def test_completion_recomputes_contact_completeness(db: Session, factory):
    """Contact should not be complete when required fields are empty."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    factory.fill_required_sections(db, app)
    db.flush()

    contact_state = next(s for s in app.section_states if s.section_key == SectionKey.contact.value)
    payload = dict(contact_state.payload or {})
    payload["region"] = ""
    contact_state.payload = payload
    contact_state.is_complete = True
    db.flush()

    pct, missing = completion_percentage(db, app)
    assert pct < 100
    assert SectionKey.contact in missing
