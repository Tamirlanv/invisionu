from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from jose import JWTError
from sqlalchemy.orm import Session

from uuid import UUID

from invision_api.api.deps import (
    blacklist_refresh_jti,
    get_current_user,
    get_refresh_token_optional,
    is_refresh_blacklisted,
    require_roles,
)
from invision_api.core.config import get_settings
from invision_api.core.security import decode_token
from invision_api.db.session import get_db
from invision_api.models.enums import RoleName
from invision_api.models.user import User
from invision_api.schemas.auth import (
    CandidateProfilePublic,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    TokenResponse,
    UserPublic,
    VerifyEmailRequest,
)
from invision_api.repositories.application_repository import get_candidate_profile_by_user
from invision_api.services import auth_service

router = APIRouter()


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    settings = get_settings()
    secure = settings.environment == "production"
    response.set_cookie(
        key="invision_access",
        value=access,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key="invision_refresh",
        value=refresh,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("invision_access", path="/")
    response.delete_cookie("invision_refresh", path="/")


@router.post("/register", response_model=TokenResponse)
def register(response: Response, body: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = auth_service.register_candidate(
        db,
        email=str(body.email),
        password=body.password,
        first_name=body.first_name,
        last_name=body.last_name,
    )
    access, refresh, _jti = auth_service.issue_tokens(user.id)
    _set_auth_cookies(response, access, refresh)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
def login(response: Response, body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = auth_service.authenticate(db, str(body.email), body.password)
    access, refresh, _jti = auth_service.issue_tokens(user.id)
    _set_auth_cookies(response, access, refresh)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/logout")
def logout(
    response: Response,
    refresh: str | None = Depends(get_refresh_token_optional),
) -> dict:
    if refresh:
        try:
            payload = decode_token(refresh)
            if payload.get("typ") == "refresh":
                jti = payload.get("jti")
                exp = payload.get("exp")
                if isinstance(jti, str) and isinstance(exp, int | float):
                    ttl = max(0, int(exp - datetime.now(tz=UTC).timestamp()))
                    blacklist_refresh_jti(jti, ttl)
        except JWTError:
            pass
    _clear_auth_cookies(response)
    return {"message": "Вы вышли из системы"}


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(
    response: Response,
    refresh: str | None = Depends(get_refresh_token_optional),
) -> TokenResponse:
    if not refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Отсутствует refresh-токен")
    try:
        payload = decode_token(refresh)
        if payload.get("typ") != "refresh":
            raise HTTPException(status_code=401, detail="Неверный refresh-токен")
        jti = payload.get("jti")
        if isinstance(jti, str) and is_refresh_blacklisted(jti):
            raise HTTPException(status_code=401, detail="Refresh-токен отозван")
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Неверный refresh-токен")
        exp = payload.get("exp")
        if isinstance(jti, str) and isinstance(exp, int | float):
            ttl = max(0, int(exp - datetime.now(tz=UTC).timestamp()))
            blacklist_refresh_jti(jti, ttl)
        uid = UUID(str(sub))
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Неверный refresh-токен") from exc

    access_t, new_refresh, _ = auth_service.issue_tokens(uid)
    _set_auth_cookies(response, access_t, new_refresh)
    return TokenResponse(access_token=access_t, refresh_token=new_refresh)


@router.get("/me", response_model=MeResponse)
def me(
    user: User = Depends(require_roles(RoleName.candidate)),
    db: Session = Depends(get_db),
) -> MeResponse:
    profile = get_candidate_profile_by_user(db, user.id)
    return MeResponse(
        user=UserPublic(
            id=user.id,
            email=user.email,
            email_verified=user.email_verified_at is not None,
        ),
        profile=None
        if not profile
        else CandidateProfilePublic(first_name=profile.first_name, last_name=profile.last_name),
    )


@router.post("/verify-email")
def verify_email(
    body: VerifyEmailRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    auth_service.verify_email(db, user.id, body.code)
    return {"message": "Email verified"}
