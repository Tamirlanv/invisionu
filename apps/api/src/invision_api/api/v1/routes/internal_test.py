from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from invision_api.api.deps import require_roles
from invision_api.db.session import get_db
from invision_api.models.enums import RoleName
from invision_api.models.user import User
from invision_api.services import internal_test_service

router = APIRouter()


class AnswerItem(BaseModel):
    question_id: UUID
    text_answer: str | None = None
    selected_options: list[Any] | None = None


class BulkAnswersBody(BaseModel):
    answers: list[AnswerItem] = Field(default_factory=list)
    consent_privacy: bool = False
    consent_parent: bool = False


@router.get("/questions")
def list_questions(
    user: User = Depends(require_roles(RoleName.candidate)),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    qs = internal_test_service.list_questions(db)
    return [
        {
            "id": str(q.id),
            "category": q.category,
            "question_type": q.question_type,
            "prompt": q.prompt,
            "options": q.options,
            "display_order": q.display_order,
            "version": q.version,
        }
        for q in qs
    ]


@router.post("/answers")
def save_answers(
    body: BulkAnswersBody,
    user: User = Depends(require_roles(RoleName.candidate)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    saved = internal_test_service.save_draft_answers(
        db,
        user,
        [a.model_dump() for a in body.answers],
        consent_privacy=body.consent_privacy,
        consent_parent=body.consent_parent,
    )
    return {"saved": len(saved), "answer_ids": [str(s.id) for s in saved]}


@router.get("/answers")
def get_answers(
    user: User = Depends(require_roles(RoleName.candidate)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return internal_test_service.get_saved_answers_state(db, user)


@router.post("/submit")
def submit_test(
    user: User = Depends(require_roles(RoleName.candidate)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    internal_test_service.submit_internal_test(db, user)
    return {"status": "submitted"}
