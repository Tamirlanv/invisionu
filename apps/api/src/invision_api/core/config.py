from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py: .../apps/api/src/invision_api/core/config.py
_API_ROOT = Path(__file__).resolve().parents[3]  # .../apps/api
_REPO_ROOT = _API_ROOT.parent.parent  # monorepo root (parent of apps/)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            str(_API_ROOT / ".env"),
            str(_REPO_ROOT / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        ...,
        description="SQLAlchemy URL, e.g. postgresql+psycopg://user:pass@host:5432/db",
    )
    redis_url: RedisDsn | str = Field(default="redis://localhost:6379/0")

    secret_key: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    cors_origins: str = "http://localhost:3000"

    upload_root: str = "./data/uploads"
    max_upload_bytes_default: int = 10 * 1024 * 1024

    resend_api_key: str | None = None
    email_from: str = "noreply@oku.com.kz"
    app_public_url: str = "http://localhost:3000"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    environment: Literal["local", "staging", "production"] = "local"

    commission_seed_email: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "COMMISSION_SEED_EMAIL",
            "COMMISSION_ADMIN_EMAIL",
            "COMMISSION_LOGIN",
        ),
        description="Commission / committee login email (bootstrap).",
    )
    commission_seed_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "COMMISSION_SEED_PASSWORD",
            "COMMISSION_ADMIN_PASSWORD",
            "COMMISSION_PASSWORD",
        ),
        description="Commission user password; in production both email and password must be set to bootstrap.",
    )
    commission_seed_role: str = Field(
        default="admin",
        validation_alias=AliasChoices("COMMISSION_SEED_ROLE"),
        description="viewer | reviewer | admin",
    )

    @field_validator("database_url")
    @classmethod
    def normalize_db_url(cls, v: str) -> str:
        if v.startswith("postgresql+asyncpg://"):
            return v.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        return v

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
