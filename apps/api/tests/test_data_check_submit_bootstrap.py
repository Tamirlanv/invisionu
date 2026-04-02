from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import AnalysisJob
from invision_api.models.application_raw_submission_snapshot import ApplicationRawSubmissionSnapshot
from invision_api.models.candidate_validation_orchestration import CandidateValidationCheck, CandidateValidationRun
from invision_api.models.commission import ApplicationStageState
from invision_api.models.enums import ApplicationStage, JobType
from invision_api.services.data_check import submit_bootstrap_service


def test_data_check_submit_bootstrap_creates_snapshot_run_and_units(
    db: Session, factory, monkeypatch
):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="in_progress")
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_args, **_kwargs: None)

    run_id = submit_bootstrap_service.bootstrap_data_check_pipeline(
        db,
        application_id=app.id,
        candidate_id=profile.id,
        actor_user_id=user.id,
    )
    db.flush()

    snapshot = db.scalars(
        select(ApplicationRawSubmissionSnapshot).where(ApplicationRawSubmissionSnapshot.application_id == app.id)
    ).first()
    assert snapshot is not None
    assert snapshot.snapshot_kind == "submitted"

    run = db.get(CandidateValidationRun, run_id)
    assert run is not None
    assert run.overall_status == "pending"

    checks = list(db.scalars(select(CandidateValidationCheck).where(CandidateValidationCheck.run_id == run_id)).all())
    assert len(checks) == 9
    queued = [c for c in checks if c.status == "queued"]
    assert len(queued) == 7

    stage_state = db.scalars(
        select(ApplicationStageState).where(
            ApplicationStageState.application_id == app.id,
            ApplicationStageState.stage == ApplicationStage.initial_screening.value,
        )
    ).first()
    assert stage_state is not None
    assert stage_state.status == "new"

    jobs = list(
        db.scalars(
            select(AnalysisJob).where(
                AnalysisJob.application_id == app.id,
                AnalysisJob.job_type == JobType.data_check_unit.value,
            )
        ).all()
    )
    assert len(jobs) == 7
