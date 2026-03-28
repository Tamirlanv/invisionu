from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from invision_api.models.application import InternalTestAnswer, InternalTestQuestion


def count_active_questions(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(InternalTestQuestion).where(InternalTestQuestion.is_active.is_(True))
        )
        or 0
    )


def list_active_questions(db: Session) -> list[InternalTestQuestion]:
    return list(
        db.scalars(
            select(InternalTestQuestion)
            .where(InternalTestQuestion.is_active.is_(True))
            .order_by(InternalTestQuestion.display_order, InternalTestQuestion.created_at)
        ).all()
    )


def get_question(db: Session, question_id: UUID) -> InternalTestQuestion | None:
    return db.get(InternalTestQuestion, question_id)


def get_answer(db: Session, application_id: UUID, question_id: UUID) -> InternalTestAnswer | None:
    return db.scalars(
        select(InternalTestAnswer).where(
            InternalTestAnswer.application_id == application_id,
            InternalTestAnswer.question_id == question_id,
        )
    ).first()


def count_finalized_answers_for_application(db: Session, application_id: UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(InternalTestAnswer)
            .where(
                InternalTestAnswer.application_id == application_id,
                InternalTestAnswer.is_finalized.is_(True),
            )
        )
        or 0
    )
