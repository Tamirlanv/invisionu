from __future__ import annotations

from datetime import UTC, datetime, timedelta
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


def test_auto_advance_blocked_when_link_and_certificate_fail(db: Session, factory, monkeypatch):
    """link_validation and certificate_validation are required; failures yield failed run; no auto-advance."""
    _, _, app, run_id = _bootstrap(db, factory, monkeypatch)

    _FAIL_UNITS = {
        DataCheckUnitType.link_validation,
        DataCheckUnitType.certificate_validation,
    }

    def _ok_processor(*_args, **_kwargs):
        return UnitExecutionResult(status="completed", payload={"ok": True})

    def _fail_processor(*_args, **_kwargs):
        return UnitExecutionResult(status="failed", errors=["simulated failure"])

    for unit in DataCheckUnitType:
        if unit in _FAIL_UNITS:
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
    assert run.overall_status == "failed"

    db.refresh(app)
    assert app.current_stage == ApplicationStage.initial_screening.value

    projection = commission_repository.get_projection(db, app.id)
    assert projection is not None
    assert projection.current_stage == ApplicationStage.initial_screening.value


def test_no_advance_when_required_unit_needs_manual_review(db: Session, factory, monkeypatch):
    """Required unit in manual_review_required yields partial run; must not auto-advance."""
    _, _, app, run_id = _bootstrap(db, factory, monkeypatch)

    def _ok(*_args, **_kwargs):
        return UnitExecutionResult(status="completed", payload={"ok": True})

    def _manual(*_args, **_kwargs):
        return UnitExecutionResult(
            status="manual_review_required",
            payload={},
            explainability=["needs human"],
        )

    for unit in DataCheckUnitType:
        monkeypatch.setitem(job_registry.REGISTRY, unit, _ok)
    monkeypatch.setitem(job_registry.REGISTRY, DataCheckUnitType.candidate_ai_summary, _manual)

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
    assert app.current_stage == ApplicationStage.initial_screening.value


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


def test_sweep_retires_noncanonical_run_and_avoids_per_run_skip_log(
    db: Session, factory, monkeypatch, caplog
):
    from invision_api.services.data_check.orchestrator_service import SWEEP_STALE_MINUTES, sweep_stuck_runs

    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="under_screening")
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    noncanonical = data_check_repository.create_run(
        db,
        candidate_id=profile.id,
        application_id=app.id,
        status="running",
    )
    data_check_repository.create_check(
        db,
        run_id=noncanonical.id,
        check_type="links",
        status="running",
        result_payload=None,
    )

    stale_time = datetime.now(tz=UTC) - timedelta(minutes=SWEEP_STALE_MINUTES + 5)
    noncanonical.updated_at = stale_time
    db.flush()

    caplog.set_level("INFO")
    recovered = sweep_stuck_runs(db)
    assert recovered >= 1

    updated_run = data_check_repository.get_run(db, noncanonical.id)
    assert updated_run is not None
    assert updated_run.overall_status == "failed"
    assert "noncanonical_run_retired" in (updated_run.errors or [])
    assert any("non-canonical" in line.lower() for line in (updated_run.explainability or []))

    all_logs = " | ".join(record.message for record in caplog.records)
    assert "sweep_skip_noncanonical run=" not in all_logs
    assert "sweep_noncanonical_summary" in all_logs


def test_list_stuck_checks_includes_stale_pending(db: Session, factory, monkeypatch):
    """Stale pending units are included so sweep can re-enqueue them like queued/running."""
    from invision_api.services.data_check.orchestrator_service import SWEEP_STALE_MINUTES

    _, _, _, run_id = _bootstrap(db, factory, monkeypatch)

    stale_time = datetime.now(tz=UTC) - timedelta(minutes=SWEEP_STALE_MINUTES + 5)
    threshold = datetime.now(tz=UTC) - timedelta(minutes=SWEEP_STALE_MINUTES)

    for check in data_check_repository.list_checks_for_run(db, run_id):
        check.status = "pending"
        check.updated_at = stale_time
    db.flush()

    stuck = data_check_repository.list_stuck_checks(db, run_id=run_id, stale_threshold=threshold)
    assert len(stuck) >= 1
    assert all(c.status == "pending" for c in stuck)


def test_run_unit_noops_when_run_already_terminal(db: Session, factory, monkeypatch):
    """Stale data_check_unit jobs must not re-run after aggregate is partial/ready/failed."""
    _, _, app, run_id = _bootstrap(db, factory, monkeypatch)

    run = data_check_repository.get_run(db, run_id)
    assert run is not None
    # Aggregate must match checks: partial only when every policy unit is terminal.
    for check in data_check_repository.list_checks_for_run(db, run_id):
        if check.check_type == DataCheckUnitType.test_profile_processing.value:
            check.status = "manual_review_required"
        else:
            check.status = "completed"
    run.overall_status = "partial"
    db.flush()

    def _must_not_run(*_a, **_k):
        raise AssertionError("processor should not run when run aggregate is terminal")

    monkeypatch.setitem(job_registry.REGISTRY, DataCheckUnitType.test_profile_processing, _must_not_run)

    job_runner_service.run_unit(
        db,
        application_id=app.id,
        run_id=run_id,
        unit_type=DataCheckUnitType.test_profile_processing,
        analysis_job_id=None,
    )

    run = data_check_repository.get_run(db, run_id)
    assert run is not None
    assert run.overall_status == "partial"


def test_run_unit_runs_when_overall_status_desynced_terminal_but_checks_incomplete(db: Session, factory, monkeypatch):
    """If overall_status is terminal but checks are not, batch must not skip — recompute from checks."""
    _, _, app, run_id = _bootstrap(db, factory, monkeypatch)

    run = data_check_repository.get_run(db, run_id)
    assert run is not None
    run.overall_status = "partial"
    db.flush()

    ran = {"n": 0}

    def _mark_ran(*_a, **_k):
        ran["n"] += 1
        return UnitExecutionResult(status="completed", payload={"ok": True})

    monkeypatch.setitem(job_registry.REGISTRY, DataCheckUnitType.test_profile_processing, _mark_ran)

    job_runner_service.run_unit(
        db,
        application_id=app.id,
        run_id=run_id,
        unit_type=DataCheckUnitType.test_profile_processing,
        analysis_job_id=None,
    )

    assert ran["n"] == 1


def test_run_unit_noops_when_unit_already_terminal(db: Session, factory, monkeypatch):
    """Duplicate queue job for a unit that already finished must not re-execute the processor."""
    _, _, app, run_id = _bootstrap(db, factory, monkeypatch)

    for check in data_check_repository.list_checks_for_run(db, run_id):
        if check.check_type == DataCheckUnitType.test_profile_processing.value:
            check.status = "completed"
        else:
            check.status = "pending"
    db.flush()

    def _must_not_run(*_a, **_k):
        raise AssertionError("processor should not run when check is already terminal")

    monkeypatch.setitem(job_registry.REGISTRY, DataCheckUnitType.test_profile_processing, _must_not_run)

    job_runner_service.run_unit(
        db,
        application_id=app.id,
        run_id=run_id,
        unit_type=DataCheckUnitType.test_profile_processing,
        analysis_job_id=None,
    )

    check = data_check_repository.get_check(db, run_id, DataCheckUnitType.test_profile_processing.value)
    assert check is not None
    assert check.status == "completed"


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


def test_sweep_reenqueues_stale_pending_first_wave(db: Session, factory, monkeypatch):
    """Stale run whose checks never left pending still gets first-wave jobs via sweep."""
    from datetime import timedelta

    from invision_api.services.data_check.job_registry import FIRST_WAVE_UNITS
    from invision_api.services.data_check.orchestrator_service import SWEEP_STALE_MINUTES, sweep_stuck_runs

    _, _, app, run_id = _bootstrap(db, factory, monkeypatch)

    run = data_check_repository.get_run(db, run_id)
    assert run is not None

    stale_time = datetime.now(tz=UTC) - timedelta(minutes=SWEEP_STALE_MINUTES + 5)
    run.updated_at = stale_time
    db.flush()

    for check in data_check_repository.list_checks_for_run(db, run_id):
        check.status = "pending"
        check.updated_at = stale_time
    db.flush()

    enqueued_units: list[str] = []

    def _track_enqueue(db_, *, application_id, run_id, unit_type, queue_report=None, strict=False):
        enqueued_units.append(unit_type.value)
        if queue_report is not None:
            queue_report.attempted += 1
            queue_report.enqueued += 1
        return uuid4()

    monkeypatch.setattr(
        "invision_api.services.job_dispatcher_service.enqueue_data_check_unit_job",
        _track_enqueue,
    )

    recovered = sweep_stuck_runs(db)
    assert recovered >= 1

    first_wave = {u.value for u in FIRST_WAVE_UNITS}
    assert any(u in first_wave for u in enqueued_units)


def test_sweep_sla_terminalizes_long_running_pipeline(db: Session, factory, monkeypatch):
    """Run past wall-clock SLA is terminalized even when updated_at is fresh (slow sequential units)."""
    from invision_api.services.data_check.orchestrator_service import (
        RUN_PROCESSING_SLA_MINUTES_DEFAULT,
        sweep_stuck_runs,
    )

    _, _, _, run_id = _bootstrap(db, factory, monkeypatch)

    run = data_check_repository.get_run(db, run_id)
    assert run is not None

    old_created = datetime.now(tz=UTC) - timedelta(minutes=RUN_PROCESSING_SLA_MINUTES_DEFAULT + 5)
    run.created_at = old_created
    run.updated_at = datetime.now(tz=UTC)
    db.flush()

    for check in data_check_repository.list_checks_for_run(db, run_id):
        check.status = "pending"
        check.updated_at = datetime.now(tz=UTC)
    db.flush()

    recovered = sweep_stuck_runs(db)
    assert recovered >= 1

    run = data_check_repository.get_run(db, run_id)
    assert run is not None
    assert run.overall_status in {"failed", "partial"}
