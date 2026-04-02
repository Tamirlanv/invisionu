from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.commission import ApplicationStageState
from invision_api.models.enums import ApplicationStage, DataCheckUnitType
from invision_api.repositories import data_check_repository
from invision_api.services.data_check import job_registry, job_runner_service, submit_bootstrap_service
from invision_api.services.data_check.contracts import UnitExecutionResult


def test_data_check_status_moves_to_in_review_when_first_unit_runs(
    db: Session, factory, monkeypatch
):
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

    def _ok(*_args, **_kwargs):
        return UnitExecutionResult(status="completed", payload={"ok": True})

    monkeypatch.setitem(job_registry.REGISTRY, DataCheckUnitType.test_profile_processing, _ok)
    job_runner_service.run_unit(
        db,
        application_id=app.id,
        run_id=run_id,
        unit_type=DataCheckUnitType.test_profile_processing,
        analysis_job_id=None,
    )
    db.flush()

    run = data_check_repository.get_run(db, run_id)
    assert run is not None
    assert run.overall_status == "running"

    check = data_check_repository.get_check(db, run_id, DataCheckUnitType.test_profile_processing.value)
    assert check is not None
    assert check.status == "completed"

    stage_state = db.scalars(
        select(ApplicationStageState).where(
            ApplicationStageState.application_id == app.id,
            ApplicationStageState.stage == ApplicationStage.initial_screening.value,
        )
    ).first()
    assert stage_state is not None
    assert stage_state.status == "in_review"
