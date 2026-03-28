from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalars(select(User).where(User.email == email.lower().strip())).first()


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    return db.get(User, user_id)
