from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import Application
from invision_api.models.commission import CommissionUser
from invision_api.models.enums import RoleName
from invision_api.models.user import Role, User, UserRole
from invision_api.repositories import admissions_repository


def load_submitted_application_or_404(db: Session, application_id: UUID) -> Application:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if not app.locked_after_submit and app.submitted_at is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return app


def resolve_commission_actions(db: Session, actor: User, *, can_advance_stage: bool) -> dict[str, Any]:
    row = db.get(CommissionUser, actor.id)
    role = row.role if row else None
    is_global_admin = False
    if role is None:
        stmt = select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == actor.id)
        global_roles = set(db.scalars(stmt).all())
        is_global_admin = RoleName.admin.value in global_roles
    is_reviewer = role in {"reviewer", "admin"} or is_global_admin
    return {
        "canComment": bool(is_reviewer),
        "canMoveForward": bool(is_reviewer and can_advance_stage),
    }

