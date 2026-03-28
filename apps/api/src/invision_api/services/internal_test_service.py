from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from invision_api.models.application import InternalTestAnswer, InternalTestQuestion
from invision_api.models.enums import ApplicationState, SectionKey
from invision_api.models.user import User
from invision_api.repositories import internal_test_repository
from invision_api.services import application_service
from invision_api.services.section_payloads import InternalTestSectionPayload


def list_questions(db: Session) -> list[InternalTestQuestion]:
    return internal_test_repository.list_active_questions(db)


def save_draft_answers(
    db: Session,
    user: User,
    answers: list[dict[str, Any]],
) -> list[InternalTestAnswer]:
    _, app = application_service.get_profile_and_application(db, user)
    application_service._ensure_editable(app)  # noqa: SLF001

    questions = {str(q.id): q for q in internal_test_repository.list_active_questions(db)}
    now = datetime.now(tz=UTC)
    out: list[InternalTestAnswer] = []

    for item in answers:
        qid = item.get("question_id")
        if not qid:
            raise HTTPException(status_code=400, detail="Для каждого ответа нужен question_id")
        q_uuid = UUID(str(qid))
        question = questions.get(str(q_uuid))
        if not question:
            raise HTTPException(status_code=400, detail=f"Неизвестный вопрос {qid}")

        existing = internal_test_repository.get_answer(db, app.id, q_uuid)
        if existing and existing.is_finalized:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ответ на вопрос {qid} уже отправлен окончательно",
            )

        text_answer = item.get("text_answer")
        selected = item.get("selected_options")

        if question.question_type == "text":
            if not text_answer or not str(text_answer).strip():
                raise HTTPException(status_code=400, detail=f"Нужен текстовый ответ на вопрос {qid}")
        elif question.question_type in ("single_choice", "multi_choice"):
            if not selected:
                raise HTTPException(status_code=400, detail=f"Нужен выбранный вариант для вопроса {qid}")

        if existing:
            existing.text_answer = text_answer
            existing.selected_options = selected
            existing.saved_at = now
            row = existing
        else:
            row = InternalTestAnswer(
                application_id=app.id,
                question_id=q_uuid,
                text_answer=text_answer,
                selected_options=selected,
                saved_at=now,
                submitted_at=None,
                is_finalized=False,
            )
            db.add(row)
        out.append(row)

    payload = InternalTestSectionPayload().model_dump()
    validated = InternalTestSectionPayload.model_validate(payload)
    is_complete = application_service.compute_section_complete(db, app, SectionKey.internal_test, validated)
    application_service.upsert_section_state(db, app, SectionKey.internal_test, payload, is_complete)
    if app.state == ApplicationState.draft.value:
        app.state = ApplicationState.in_progress.value

    db.commit()
    for r in out:
        db.refresh(r)
    return out


def submit_internal_test(db: Session, user: User) -> None:
    _, app = application_service.get_profile_and_application(db, user)
    application_service._ensure_editable(app)  # noqa: SLF001

    questions = internal_test_repository.list_active_questions(db)
    if not questions:
        raise HTTPException(status_code=503, detail="Внутренний тест не настроен")

    now = datetime.now(tz=UTC)
    for q in questions:
        ans = internal_test_repository.get_answer(db, app.id, q.id)
        if not ans:
            raise HTTPException(
                status_code=400,
                detail=f"Нет ответа на вопрос {q.id}",
            )
        if ans.is_finalized:
            continue
        if q.question_type == "text" and (not ans.text_answer or not ans.text_answer.strip()):
            raise HTTPException(status_code=400, detail=f"Неполный текстовый ответ на вопрос {q.id}")
        if q.question_type != "text" and not ans.selected_options:
            raise HTTPException(status_code=400, detail=f"Неполный выбор вариантов для вопроса {q.id}")
        ans.submitted_at = now
        ans.is_finalized = True

    payload = InternalTestSectionPayload().model_dump()
    validated = InternalTestSectionPayload.model_validate(payload)
    is_complete = application_service.compute_section_complete(db, app, SectionKey.internal_test, validated)
    application_service.upsert_section_state(db, app, SectionKey.internal_test, payload, is_complete)
    db.commit()
