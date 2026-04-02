from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from invision_api.commission.application.personal_info_service import (
    get_commission_application_personal_info,
)
from invision_api.commission.application.personal_info_validators import resolve_commission_actions
from invision_api.models.commission import CommissionUser
from invision_api.models.enums import ApplicationState
from invision_api.models.user import Role


def test_actions_for_viewer_reviewer_and_admin(db: Session, factory):
    committee_role = factory.committee_role(db)

    viewer = factory.user(db)
    factory.assign_role(db, viewer, committee_role)
    db.add(CommissionUser(user_id=viewer.id, role="viewer"))

    reviewer = factory.user(db)
    factory.assign_role(db, reviewer, committee_role)
    db.add(CommissionUser(user_id=reviewer.id, role="reviewer"))

    admin_user = factory.user(db)
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if not admin_role:
        admin_role = Role(id=uuid4(), name="admin")
        db.add(admin_role)
        db.flush()
    factory.assign_role(db, admin_user, admin_role)
    db.flush()

    viewer_actions = resolve_commission_actions(db, viewer, can_advance_stage=True)
    reviewer_actions = resolve_commission_actions(db, reviewer, can_advance_stage=True)
    admin_actions = resolve_commission_actions(db, admin_user, can_advance_stage=True)

    assert viewer_actions == {"canComment": False, "canMoveForward": False}
    assert reviewer_actions == {"canComment": True, "canMoveForward": True}
    assert admin_actions == {"canComment": True, "canMoveForward": True}


def test_personal_info_opens_on_any_post_submit_stage(db: Session, factory):
    """After stage-gate removal, personal-info must return 200 on any stage."""
    committee_user = factory.user(db)
    committee_role = factory.committee_role(db)
    factory.assign_role(db, committee_user, committee_role)
    db.add(CommissionUser(user_id=committee_user.id, role="reviewer"))

    candidate_user = factory.user(db)
    profile = factory.profile(db, candidate_user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.locked_after_submit = True
    app.submitted_at = datetime.now(tz=UTC)
    app.current_stage = "committee_review"
    db.flush()

    result = get_commission_application_personal_info(db, application_id=app.id, actor=committee_user)
    assert result["applicationId"] == str(app.id)
    assert result["candidateSummary"]["currentStage"] == "committee_decision"


def test_personal_info_returns_processing_status_on_initial_screening(db: Session, factory):
    """On initial_screening, processingStatus should be present (null if no run)."""
    committee_user = factory.user(db)
    committee_role = factory.committee_role(db)
    factory.assign_role(db, committee_user, committee_role)
    db.add(CommissionUser(user_id=committee_user.id, role="reviewer"))

    candidate_user = factory.user(db)
    profile = factory.profile(db, candidate_user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.locked_after_submit = True
    app.submitted_at = datetime.now(tz=UTC)
    app.current_stage = "initial_screening"
    db.flush()

    result = get_commission_application_personal_info(db, application_id=app.id, actor=committee_user)
    assert result["applicationId"] == str(app.id)
    assert result["candidateSummary"]["currentStage"] == "data_check"
    # No data-check run created yet, so processingStatus is null
    assert result["processingStatus"] is None


def test_advance_not_allowed_on_initial_screening(db: Session, factory):
    """canMoveForward must be False when stage is initial_screening."""
    committee_user = factory.user(db)
    committee_role = factory.committee_role(db)
    factory.assign_role(db, committee_user, committee_role)
    db.add(CommissionUser(user_id=committee_user.id, role="reviewer"))

    candidate_user = factory.user(db)
    profile = factory.profile(db, candidate_user)
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.locked_after_submit = True
    app.submitted_at = datetime.now(tz=UTC)
    app.current_stage = "initial_screening"
    db.flush()

    result = get_commission_application_personal_info(db, application_id=app.id, actor=committee_user)
    assert result["actions"]["canMoveForward"] is False
    assert result["actions"]["canComment"] is True
