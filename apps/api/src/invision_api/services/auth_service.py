from datetime import UTC, datetime, timedelta
from uuid import UUID

import resend
from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from invision_api.core.config import get_settings
from invision_api.core.security import (
    create_access_token,
    create_refresh_token,
    generate_email_verification_code,
    hash_email_code,
    hash_password,
    verify_password,
)
from invision_api.models.application import CandidateProfile
from invision_api.models.enums import RoleName, VerificationType
from invision_api.models.user import User, UserRole
from invision_api.models.application import VerificationRecord
from invision_api.repositories import role_repository, user_repository
from invision_api.repositories.application_repository import create_initial_application


def _send_verification_email(to_email: str, code: str) -> None:
    settings = get_settings()
    if not settings.resend_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Отправка почты не настроена (RESEND_API_KEY).",
        )
    resend.api_key = settings.resend_api_key
    params = {
        "from": settings.email_from,
        "to": [to_email],
        "subject": "Подтверждение аккаунта inVision U",
        "html": f"<p>Ваш код подтверждения: <strong>{code}</strong></p><p>Код действителен 24 часа.</p>",
    }
    resend.Emails.send(params)


def register_candidate(
    db: Session,
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
) -> User:
    normalized = email.lower().strip()
    if user_repository.get_user_by_email(db, normalized):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Этот email уже зарегистрирован")

    code = generate_email_verification_code()
    code_hash = hash_email_code(code)
    expires = datetime.now(tz=UTC) + timedelta(hours=24)

    user = User(
        email=normalized,
        hashed_password=hash_password(password),
        is_active=True,
        email_verification_code_hash=code_hash,
        email_verification_expires_at=expires,
    )
    db.add(user)
    db.flush()

    profile = CandidateProfile(user_id=user.id, first_name=first_name.strip(), last_name=last_name.strip())
    db.add(profile)
    db.flush()  # assign profile.id before Application FK (defaults run at INSERT, not on add())

    role = role_repository.ensure_role(db, RoleName.candidate)
    db.add(UserRole(user_id=user.id, role_id=role.id))

    create_initial_application(db, profile.id)

    vr = VerificationRecord(
        user_id=user.id,
        verification_type=VerificationType.email.value,
        status="pending",
        payload={"purpose": "registration"},
    )
    db.add(vr)

    try:
        _send_verification_email(normalized, code)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Не удалось отправить письмо с кодом: {exc}",
        ) from exc

    db.commit()
    db.refresh(user)
    return user


def verify_email(db: Session, user_id: UUID, code: str) -> User:
    user = user_repository.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    if user.email_verified_at:
        return user
    if not user.email_verification_code_hash or not user.email_verification_expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нет ожидающего подтверждения")
    if user.email_verification_expires_at < datetime.now(tz=UTC):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Срок действия кода истёк")
    if hash_email_code(code) != user.email_verification_code_hash:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный код подтверждения")

    user.email_verified_at = datetime.now(tz=UTC)
    user.email_verification_code_hash = None
    user.email_verification_expires_at = None

    db.execute(
        update(VerificationRecord)
        .where(VerificationRecord.user_id == user.id)
        .where(VerificationRecord.verification_type == VerificationType.email.value)
        .where(VerificationRecord.status == "pending")
        .values(status="verified")
    )

    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = user_repository.get_user_by_email(db, email.lower().strip())
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Аккаунт отключён")
    return user


def issue_tokens(user_id: UUID) -> tuple[str, str, str]:
    sub = str(user_id)
    access = create_access_token(sub)
    refresh, jti = create_refresh_token(sub)
    return access, refresh, jti
