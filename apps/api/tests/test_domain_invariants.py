"""Tests for critical domain invariants across the pipeline."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import Application, AuditLog
from invision_api.models.enums import ApplicationStage
from invision_api.services.application_service import save_section, submit_application
from invision_api.models.enums import SectionKey


def _mock_pipeline_ready(monkeypatch) -> None:
    monkeypatch.setattr("invision_api.services.application_service.redis_ping", lambda: True)
    monkeypatch.setattr(
        "invision_api.services.application_service.get_redis_client",
        lambda: type("_R", (), {"exists": lambda self, *_a: 1})(),
    )
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_args, **_kwargs: None)


def test_invariant_submitted_implies_locked(db: Session, factory, monkeypatch):
    """INV-1: submitted_at IS NOT NULL implies locked_after_submit = True."""
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
        result = submit_application(db, user)
        assert result.submitted_at is not None
        assert result.locked_after_submit is True
    finally:
        iss.enqueue_post_submit_jobs = original


def test_invariant_locked_rejects_edits(db: Session, factory):
    """INV-2: locked_after_submit = True rejects all PATCH calls with 409."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    app.locked_after_submit = True
    db.commit()

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        save_section(db, user, SectionKey.personal, {"preferred_first_name": "X", "preferred_last_name": "Y"})
    assert exc.value.status_code == 409


def test_invariant_submit_creates_audit_log(db: Session, factory, monkeypatch):
    """INV-7: Submit creates an audit log entry."""
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
        logs = list(db.scalars(
            select(AuditLog)
            .where(AuditLog.entity_id == app.id, AuditLog.action == "application_submitted")
        ).all())
        assert len(logs) >= 1
    finally:
        iss.enqueue_post_submit_jobs = original


def test_invariant_duplicate_submit_blocked(db: Session, factory, monkeypatch):
    """INV-6: Duplicate submit returns 409."""
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
        with pytest.raises(HTTPException) as exc:
            submit_application(db, user)
        assert exc.value.status_code == 409
    finally:
        iss.enqueue_post_submit_jobs = original
