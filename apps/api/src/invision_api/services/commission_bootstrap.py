"""Idempotent bootstrap for commission / committee login user from Settings."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.core.config import Settings
from invision_api.core.security import hash_password
from invision_api.models.commission import CommissionUser
from invision_api.models.enums import RoleName
from invision_api.models.user import User, UserRole
from invision_api.repositories import user_repository
from invision_api.repositories.role_repository import ensure_role

log = logging.getLogger(__name__)

_DEFAULT_DEV_EMAIL = "commission@example.com"
_DEFAULT_DEV_PASSWORD = "DevCommission123!"


def _effective_commission_role(settings: Settings) -> str:
    role = (settings.commission_seed_role or "admin").strip().lower()
    if role not in {"viewer", "reviewer", "admin"}:
        raise ValueError("COMMISSION_SEED_ROLE must be one of: viewer|reviewer|admin")
    return role


def _resolve_bootstrap_credentials(
    settings: Settings,
) -> tuple[str, str, bool, bool]:
    """
    Returns (email, password, should_run, password_explicit_for_update).
    If should_run is False, skip bootstrap entirely.
    password_explicit_for_update: if True and user exists, rotate password.
    """
    raw_email = settings.commission_seed_email
    raw_password = settings.commission_seed_password

    email_explicit = raw_email is not None and str(raw_email).strip() != ""
    password_explicit = raw_password is not None and str(raw_password).strip() != ""

    if settings.environment == "production":
        if not email_explicit or not password_explicit:
            return ("", "", False, False)
        return (
            str(raw_email).strip().lower(),
            str(raw_password).strip(),
            True,
            True,
        )

    # local / staging: allow dev defaults when unset
    email = str(raw_email).strip().lower() if email_explicit else _DEFAULT_DEV_EMAIL
    password = str(raw_password).strip() if password_explicit else _DEFAULT_DEV_PASSWORD
    return (email, password, True, password_explicit)


def ensure_commission_user_from_env(db: Session, settings: Settings) -> None:
    """
    Create or update commission user from env (idempotent). Commits on success.

    In production, requires explicit email and password via Settings (no dev defaults).
    In local/staging, uses default email/password when env vars are unset.
    """
    email, seed_password, should_run, password_explicit = _resolve_bootstrap_credentials(settings)
    if not should_run:
        log.info(
            "commission_bootstrap: skipped in production (set COMMISSION_SEED_EMAIL or "
            "COMMISSION_ADMIN_EMAIL and a matching password env var to enable)"
        )
        return

    commission_role = _effective_commission_role(settings)

    user = user_repository.get_user_by_email(db, email)
    if not user:
        user = User(
            email=email,
            hashed_password=hash_password(seed_password),
            is_active=True,
            email_verified_at=datetime.now(tz=UTC),
        )
        db.add(user)
        db.flush()
        log.info("commission_bootstrap: created commission user %s", email)
    else:
        user.is_active = True
        if not user.email_verified_at:
            user.email_verified_at = datetime.now(tz=UTC)
        if password_explicit:
            user.hashed_password = hash_password(seed_password)
            log.info("commission_bootstrap: updated commission user password %s", email)

    global_role = RoleName.admin if commission_role == "admin" else RoleName.committee
    role = ensure_role(db, global_role)
    existing_user_role = db.scalars(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
    ).first()
    if not existing_user_role:
        db.add(UserRole(user_id=user.id, role_id=role.id))

    comm = db.get(CommissionUser, user.id)
    if not comm:
        db.add(CommissionUser(user_id=user.id, role=commission_role))
    else:
        comm.role = commission_role

    db.commit()
    log.info("commission_bootstrap: ensured commission role %s -> %s", email, commission_role)
