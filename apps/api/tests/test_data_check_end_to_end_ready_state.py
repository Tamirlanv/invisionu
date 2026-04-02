from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import Application
from invision_api.models.commission import ApplicationStageState
from invision_api.models.enums import ApplicationStage, ApplicationState, DataCheckUnitType
from invision_api.repositories import commission_repository, data_check_repository
from invision_api.services import job_dispatcher_service
from invision_api.services.data_check import job_registry, job_runner_service, submit_bootstrap_service
from invision_api.services.data_check.contracts import UnitExecutionResult


_EXECUTION_ORDER = (
    DataCheckUnitType.test_profile_processing,
    DataCheckUnitType.motivation_processing,
    DataCheckUnitType.growth_path_processing,
    DataCheckUnitType.achievements_processing,
    DataCheckUnitType.link_validation,
    DataCheckUnitType.video_validation,
    DataCheckUnitType.certificate_validation,
    DataCheckUnitType.signals_aggregation,
    DataCheckUnitType.candidate_ai_summary,
)


def _bootstrap(db, factory, monkeypatch):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_args, **_kwargs: None)

    run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )
    return user, profile, app, run_id


def test_data_check_end_to_end_ready_state(db: Session, factory, monkeypatch):
    user, profile, app, run_id = _bootstrap(db, factory, monkeypatch)

    def _ok(*_args, **_kwargs):
        return UnitExecutionResult(status="completed", payload={"ok": True})

    for unit in DataCheckUnitType:
        monkeypatch.setitem(job_registry.REGISTRY, unit, _ok)

    for unit in _EXECUTION_ORDER:
        job_runner_service.run_unit(
            db,
            application_id=app.id,
            run_id=run_id,
            unit_type=unit,
            analysis_job_id=None,
        )

    run = data_check_repository.get_run(db, run_id)
    assert run is not None
    assert run.overall_status == "ready"

    stage_state = db.scalars(
        select(ApplicationStageState).where(
            ApplicationStageState.application_id == app.id,
            ApplicationStageState.stage == ApplicationStage.initial_screening.value,
        )
    ).first()
    assert stage_state is not None
    assert stage_state.status == "approved"
    assert stage_state.attention_flag_manual is False

    db.refresh(app)
    assert app.current_stage == ApplicationStage.application_review.value

    projection = commission_repository.get_projection(db, app.id)
    assert projection is not None
    assert projection.current_stage == ApplicationStage.application_review.value


def test_auto_advance_to_application_review_on_ready(db: Session, factory, monkeypatch):
    """When all units complete successfully, application auto-advances
    from initial_screening to application_review."""
    _, _, app, run_id = _bootstrap(db, factory, monkeypatch)

    def _ok(*_args, **_kwargs):
        return UnitExecutionResult(status="completed", payload={"ok": True})

    for unit in DataCheckUnitType:
        monkeypatch.setitem(job_registry.REGISTRY, unit, _ok)

    for unit in _EXECUTION_ORDER:
        job_runner_service.run_unit(
            db,
            application_id=app.id,
            run_id=run_id,
            unit_type=unit,
            analysis_job_id=None,
        )

    db.refresh(app)
    assert app.current_stage == ApplicationStage.application_review.value
    assert app.state == ApplicationState.under_review.value

    projection = commission_repository.get_projection(db, app.id)
    assert projection is not None
    assert projection.current_stage == ApplicationStage.application_review.value


def test_auto_advance_on_partial_optional_failures(db: Session, factory, monkeypatch):
    """When only optional units fail but all required units complete,
    application still auto-advances to application_review (partial status)."""
    _, _, app, run_id = _bootstrap(db, factory, monkeypatch)

    _OPTIONAL_UNITS = {
        DataCheckUnitType.link_validation,
        DataCheckUnitType.video_validation,
        DataCheckUnitType.certificate_validation,
    }

    def _ok_processor(*_args, **_kwargs):
        return UnitExecutionResult(status="completed", payload={"ok": True})

    def _fail_processor(*_args, **_kwargs):
        return UnitExecutionResult(status="failed", errors=["simulated failure"])

    for unit in DataCheckUnitType:
        if unit in _OPTIONAL_UNITS:
            monkeypatch.setitem(job_registry.REGISTRY, unit, _fail_processor)
        else:
            monkeypatch.setitem(job_registry.REGISTRY, unit, _ok_processor)

    for unit in _EXECUTION_ORDER:
        job_runner_service.run_unit(
            db,
            application_id=app.id,
            run_id=run_id,
            unit_type=unit,
            analysis_job_id=None,
        )

    run = data_check_repository.get_run(db, run_id)
    assert run is not None
    assert run.overall_status == "partial"

    db.refresh(app)
    assert app.current_stage == ApplicationStage.application_review.value
    assert app.state == ApplicationState.under_review.value

    projection = commission_repository.get_projection(db, app.id)
    assert projection is not None
    assert projection.current_stage == ApplicationStage.application_review.value


def test_no_advance_on_required_failure(db: Session, factory, monkeypatch):
    """When a required unit fails, application stays on initial_screening."""
    _, _, app, run_id = _bootstrap(db, factory, monkeypatch)

    def _ok(*_args, **_kwargs):
        return UnitExecutionResult(status="completed", payload={"ok": True})

    def _fail(*_args, **_kwargs):
        return UnitExecutionResult(status="failed", errors=["required failure"])

    for unit in DataCheckUnitType:
        monkeypatch.setitem(job_registry.REGISTRY, unit, _ok)
    monkeypatch.setitem(job_registry.REGISTRY, DataCheckUnitType.motivation_processing, _fail)

    for unit in _EXECUTION_ORDER:
        job_runner_service.run_unit(
            db,
            application_id=app.id,
            run_id=run_id,
            unit_type=unit,
            analysis_job_id=None,
        )

    run = data_check_repository.get_run(db, run_id)
    assert run is not None
    assert run.overall_status == "failed"

    db.refresh(app)
    assert app.current_stage == ApplicationStage.initial_screening.value


def test_sweep_recovers_stuck_queued_units(db: Session, factory, monkeypatch):
    """sweep_stuck_runs re-enqueues checks stuck in 'queued' past the stale threshold."""
    from datetime import timedelta

    from invision_api.services.data_check.orchestrator_service import SWEEP_STALE_MINUTES, sweep_stuck_runs

    _, _, app, run_id = _bootstrap(db, factory, monkeypatch)

    run = data_check_repository.get_run(db, run_id)
    assert run is not None

    stale_time = datetime.now(tz=UTC) - timedelta(minutes=SWEEP_STALE_MINUTES + 5)
    run.updated_at = stale_time
    db.flush()

    checks = data_check_repository.list_checks_for_run(db, run_id)
    for check in checks:
        check.status = "queued"
        check.updated_at = stale_time
    db.flush()

    enqueued_units: list[str] = []
    original_enqueue = job_dispatcher_service.enqueue_data_check_unit_job.__wrapped__ if hasattr(
        job_dispatcher_service.enqueue_data_check_unit_job, "__wrapped__"
    ) else None

    def _track_enqueue(db_, *, application_id, run_id, unit_type, queue_report=None, strict=False):
        enqueued_units.append(unit_type.value)
        return uuid4()

    monkeypatch.setattr(
        "invision_api.services.job_dispatcher_service.enqueue_data_check_unit_job",
        _track_enqueue,
    )

    recovered = sweep_stuck_runs(db)
    assert recovered >= 1

    for check in data_check_repository.list_checks_for_run(db, run_id):
        assert check.status in {"queued", "pending"}

    assert len(enqueued_units) > 0


def test_sweep_marks_failed_after_max_attempts(db: Session, factory, monkeypatch):
    """sweep_stuck_runs marks checks as failed when they exceed max_attempts."""
    from datetime import timedelta

    from invision_api.services.data_check.orchestrator_service import SWEEP_STALE_MINUTES, sweep_stuck_runs

    _, _, app, run_id = _bootstrap(db, factory, monkeypatch)

    run = data_check_repository.get_run(db, run_id)
    assert run is not None

    stale_time = datetime.now(tz=UTC) - timedelta(minutes=SWEEP_STALE_MINUTES + 5)
    run.updated_at = stale_time
    db.flush()

    checks = data_check_repository.list_checks_for_run(db, run_id)
    for check in checks:
        check.status = "running"
        check.attempts = 5
        check.updated_at = stale_time
    db.flush()

    recovered = sweep_stuck_runs(db)
    assert recovered >= 1

    for check in data_check_repository.list_checks_for_run(db, run_id):
        assert check.status == "failed"
        assert "exceeded_max_attempts" in (check.last_error or "")
