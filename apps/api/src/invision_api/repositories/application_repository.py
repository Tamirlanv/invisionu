from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from invision_api.models.application import (
    Application,
    ApplicationStageHistory,
    CandidateProfile,
)
from invision_api.models.enums import ApplicationStage, ApplicationState, StageActorType


def get_candidate_profile_by_user(db: Session, user_id: UUID) -> CandidateProfile | None:
    return db.scalars(select(CandidateProfile).where(CandidateProfile.user_id == user_id)).first()


def get_application_for_candidate(db: Session, candidate_profile_id: UUID) -> Application | None:
    return db.scalars(
        select(Application)
        .where(
            Application.candidate_profile_id == candidate_profile_id,
            Application.is_archived.is_(False),
        )
        .options(
            selectinload(Application.section_states),
            selectinload(Application.stage_history),
            selectinload(Application.education_records),
            selectinload(Application.documents),
            selectinload(Application.internal_test_answers),
        )
    ).first()


def get_application_by_id(db: Session, application_id: UUID) -> Application | None:
    return db.scalars(
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.section_states),
            selectinload(Application.stage_history),
            selectinload(Application.education_records),
            selectinload(Application.documents),
            selectinload(Application.internal_test_answers),
        )
    ).first()


def create_initial_application(db: Session, candidate_profile_id: UUID) -> Application:
    now = datetime.now(tz=UTC)
    app = Application(
        candidate_profile_id=candidate_profile_id,
        state=ApplicationState.draft.value,
        current_stage=ApplicationStage.application.value,
        locked_after_submit=False,
        is_archived=False,
    )
    db.add(app)
    db.flush()
    history = ApplicationStageHistory(
        application_id=app.id,
        from_stage=None,
        to_stage=ApplicationStage.application.value,
        entered_at=now,
        actor_type=StageActorType.system.value,
        candidate_visible_note="Your application has been created.",
    )
    db.add(history)
    return app
