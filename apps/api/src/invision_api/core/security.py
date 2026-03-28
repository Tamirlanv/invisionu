import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from invision_api.core.config import get_settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_email_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def generate_email_verification_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.now(tz=UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode = {"sub": subject, "typ": "access", "exp": expire}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> tuple[str, str]:
    """
    Returns (jwt, jti) for optional revocation list.
    """
    settings = get_settings()
    jti = str(uuid.uuid4())
    expire = datetime.now(tz=UTC) + timedelta(days=settings.refresh_token_expire_days)
    to_encode = {"sub": subject, "typ": "refresh", "jti": jti, "exp": expire}
    token = jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, jti


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
