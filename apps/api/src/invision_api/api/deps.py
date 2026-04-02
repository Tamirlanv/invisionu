from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.core.redis_client import get_redis_client
from invision_api.commission.domain.types import CommissionRole
from invision_api.core.security import decode_token
from invision_api.db.session import get_db
from invision_api.models.commission import CommissionUser
from invision_api.models.enums import RoleName
from invision_api.models.user import Role, User, UserRole


def get_token_from_request(
    authorization: Annotated[str | None, Header()] = None,
    invision_access: Annotated[str | None, Cookie()] = None,
) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return invision_access


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str | None, Depends(get_token_from_request)],
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")
    try:
        payload = decode_token(token)
        if payload.get("typ") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный тип токена")
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный токен")
        user_id = UUID(sub)
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный токен")

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь неактивен")
    return user


def require_roles(*roles: RoleName) -> Callable[..., User]:
    def _dep(
        db: Annotated[Session, Depends(get_db)],
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        allowed = {r.value for r in roles}
        stmt = select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
        user_role_names = set(db.scalars(stmt).all())
        if not allowed.intersection(user_role_names):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
        return user

    return _dep


_COMMISSION_ROLE_LEVEL: dict[str, int] = {
    CommissionRole.viewer.value: 1,
    CommissionRole.reviewer.value: 2,
    CommissionRole.admin.value: 3,
}


def require_commission_role(min_role: CommissionRole) -> Callable[..., User]:
    """
    Two-layer guard:
    1) global role must be committee/admin
    2) commission_users.role must be >= min_role
    """

    def _dep(
        db: Annotated[Session, Depends(get_db)],
        user: Annotated[User, Depends(require_roles(RoleName.committee, RoleName.admin))],
    ) -> User:
        row = db.get(CommissionUser, user.id)
        if not row:
            # Bootstrap fallback: global admin is treated as commission admin.
            role_stmt = select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
            global_roles = set(db.scalars(role_stmt).all())
            if RoleName.admin.value in global_roles:
                return user
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет роли комиссии")
        want = _COMMISSION_ROLE_LEVEL[min_role.value]
        have = _COMMISSION_ROLE_LEVEL.get(row.role, 0)
        if have < want:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав комиссии")
        return user

    return _dep


def get_refresh_token_optional(
    invision_refresh: Annotated[str | None, Cookie()] = None,
    x_refresh_token: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> str | None:
    if x_refresh_token:
        return x_refresh_token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return invision_refresh


def is_refresh_blacklisted(jti: str) -> bool:
    key = f"refresh_token_blacklist:{jti}"
    try:
        r = get_redis_client()
        return bool(r.exists(key))
    except Exception:
        return False


def blacklist_refresh_jti(jti: str, ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        return
    key = f"refresh_token_blacklist:{jti}"
    try:
        r = get_redis_client()
        r.setex(key, ttl_seconds, "1")
    except Exception:
        # Dev-safe fallback: if Redis is unavailable, do not fail auth endpoints with 500.
        # Token revocation via blacklist becomes best-effort until Redis is restored.
        return
