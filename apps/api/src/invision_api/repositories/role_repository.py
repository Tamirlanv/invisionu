from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.enums import RoleName
from invision_api.models.user import Role


def get_role_by_name(db: Session, name: RoleName) -> Role | None:
    return db.scalars(select(Role).where(Role.name == name.value)).first()


def ensure_role(db: Session, name: RoleName) -> Role:
    role = get_role_by_name(db, name)
    if role:
        return role
    role = Role(name=name.value)
    db.add(role)
    db.flush()
    return role
