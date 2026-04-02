from datetime import UTC, datetime
from sqlalchemy.orm import Session

from invision_api.commission.application.personal_info_service import get_commission_application_personal_info
from invision_api.models.application import ApplicationSectionState
from invision_api.models.commission import CommissionUser
from invision_api.models.enums import ApplicationState


def test_personal_info_read_model_sections_are_mapped(db: Session, factory):
    committee_user = factory.user(db)
    committee_role = factory.committee_role(db)
    factory.assign_role(db, committee_user, committee_role)
    db.add(CommissionUser(user_id=committee_user.id, role="reviewer"))

    candidate_user = factory.user(db)
    profile = factory.profile(db, candidate_user, first_name="Иван", last_name="Иванов")
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = "application_review"
    app.locked_after_submit = True
    app.submitted_at = datetime.now(tz=UTC)

    db.add(
        ApplicationSectionState(
            application_id=app.id,
            section_key="personal",
            payload={
                "preferred_first_name": "Иван",
                "preferred_last_name": "Иванов",
                "middle_name": "Иванович",
                "gender": "Мужской",
                "date_of_birth": "2007-04-10",
                "father_last": "Иванов",
                "father_first": "Петр",
                "father_phone": "+77010000001",
                "mother_last": "Иванова",
                "mother_first": "Мария",
                "mother_phone": "+77010000002",
            },
            is_complete=True,
            schema_version=1,
            last_saved_at=datetime.now(tz=UTC),
        )
    )
    db.add(
        ApplicationSectionState(
            application_id=app.id,
            section_key="contact",
            payload={
                "phone_e164": "+77029590338",
                "instagram": "@ivan",
                "telegram": "@ivannnnn3",
                "whatsapp": "+77029590338",
                "country": "KZ",
                "region": "Алматы",
                "city": "Алматы",
                "address_line1": "Алматы, Абая 15, кв 43",
            },
            is_complete=True,
            schema_version=1,
            last_saved_at=datetime.now(tz=UTC),
        )
    )
    db.add(
        ApplicationSectionState(
            application_id=app.id,
            section_key="education",
            payload={"presentation_video_url": "https://www.youtube.com/watch?v=abc"},
            is_complete=True,
            schema_version=1,
            last_saved_at=datetime.now(tz=UTC),
        )
    )
    db.flush()

    view = get_commission_application_personal_info(db, application_id=app.id, actor=committee_user)

    assert view["applicationId"] == str(app.id)
    assert view["candidateSummary"]["fullName"] == "Иван Иванов"
    assert view["candidateSummary"]["currentStage"] == "application_review"
    assert view["personalInfo"]["basicInfo"]["gender"] == "Мужской"
    assert view["personalInfo"]["basicInfo"]["birthDate"] == "2007-04-10"
    assert view["personalInfo"]["contacts"]["telegram"] == "@ivannnnn3"
    assert view["personalInfo"]["address"]["fullAddress"] == "Алматы, Абая 15, кв 43"
    assert len(view["personalInfo"]["guardians"]) == 2
    assert view["personalInfo"]["videoPresentation"]["url"] == "https://www.youtube.com/watch?v=abc"
    assert view["actions"]["canComment"] is True
    assert view["actions"]["canMoveForward"] is True

