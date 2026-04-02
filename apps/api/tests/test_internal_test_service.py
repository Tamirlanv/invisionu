from uuid import uuid4

from sqlalchemy.orm import Session

from invision_api.models.application import InternalTestQuestion
from invision_api.models.enums import QuestionCategory, QuestionType, SectionKey
from invision_api.services import application_service, internal_test_service


def _create_question(db: Session, idx: int) -> InternalTestQuestion:
    q = InternalTestQuestion(
        id=uuid4(),
        category=QuestionCategory.leadership_scenarios.value,
        question_type=QuestionType.single_choice.value,
        prompt=f"Q{idx}",
        options=[
            {"id": "A", "label": "A"},
            {"id": "B", "label": "B"},
            {"id": "C", "label": "C"},
            {"id": "D", "label": "D"},
        ],
        display_order=idx,
        is_active=True,
        version=1,
    )
    db.add(q)
    db.flush()
    return q


def test_save_draft_answers_marks_internal_test_complete_when_all_answered(db: Session, factory):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    questions = internal_test_service.list_questions(db)
    if not questions:
        questions = [_create_question(db, 1), _create_question(db, 2)]
    db.commit()

    internal_test_service.save_draft_answers(
        db,
        user,
        answers=[{"question_id": str(q.id), "selected_options": ["A"]} for q in questions],
        consent_privacy=True,
        consent_parent=True,
    )

    db.refresh(app)
    st = next((s for s in app.section_states if s.section_key == SectionKey.internal_test.value), None)
    assert st is not None
    assert st.is_complete is True

    pct, missing = application_service.completion_percentage(db, app)
    assert pct > 0
    assert SectionKey.internal_test not in missing


def test_get_saved_answers_state_returns_answers_and_consents(db: Session, factory):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    questions = internal_test_service.list_questions(db)
    q1 = questions[0] if questions else _create_question(db, 10)
    db.commit()

    internal_test_service.save_draft_answers(
        db,
        user,
        answers=[{"question_id": str(q1.id), "selected_options": ["C"]}],
        consent_privacy=True,
        consent_parent=True,
    )

    state = internal_test_service.get_saved_answers_state(db, user)
    assert state["consent_privacy"] is True
    assert state["consent_parent"] is True
    assert len(state["answers"]) == 1
    assert state["answers"][0]["question_id"] == str(q1.id)
    assert state["answers"][0]["selected_options"] == ["C"]
