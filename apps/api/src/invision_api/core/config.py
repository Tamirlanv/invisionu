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

    upload_root: str = Field(
        default="./data/uploads",
        validation_alias=AliasChoices("UPLOAD_ROOT", "upload_root"),
        description=(
            "Directory for LocalStorageBackend; must match API and worker in deployment. "
            "Relative paths are resolved against the monorepo root (not process cwd) so API and worker "
            "share the same files when both use e.g. UPLOAD_ROOT=./data/uploads."
        ),
    )
    max_upload_bytes_default: int = 10 * 1024 * 1024
    storage_read_mode: Literal["local_only", "local_then_proxy"] = Field(
        default="local_only",
        validation_alias=AliasChoices("STORAGE_READ_MODE"),
        description=(
            "Storage read strategy. local_only: read only local UPLOAD_ROOT. "
            "local_then_proxy: on local miss, fetch bytes via internal API storage-proxy endpoint."
        ),
    )
    storage_proxy_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("STORAGE_PROXY_BASE_URL"),
        description="Base URL for API storage-proxy endpoint used by workers in local_then_proxy mode.",
    )
    storage_proxy_shared_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("STORAGE_PROXY_SHARED_SECRET"),
        description="Shared secret sent by worker as X-Storage-Proxy-Secret to API storage-proxy endpoint.",
    )
    storage_proxy_timeout_seconds: float = Field(
        default=15.0,
        validation_alias=AliasChoices("STORAGE_PROXY_TIMEOUT_SECONDS"),
        description="HTTP timeout for storage-proxy fetch requests.",
    )
    internal_storage_proxy_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INTERNAL_STORAGE_PROXY_SECRET"),
        description="API-side shared secret required for /internal/processing/storage/* endpoints.",
    )

    resend_api_key: str | None = None
    email_from: str = "noreply@oku.com.kz"
    app_public_url: str = "http://localhost:3000"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    environment: Literal["local", "staging", "production"] = "local"

    ai_interview_allow_internal_transition_bypass: bool = Field(
        default=False,
        validation_alias=AliasChoices("AI_INTERVIEW_ALLOW_INTERNAL_TRANSITION_BYPASS"),
        description=(
            "Break-glass only (local/staging). When true, TransitionName.review_complete may skip the "
            "commission-approved AI question set check (see transition_to_interview). "
            "Ignored in practice when ENVIRONMENT=production: bypass transitions are always rejected. "
            "Must be false in production."
        ),
    )
    ai_interview_require_data_ready: bool = Field(
        default=False,
        validation_alias=AliasChoices("AI_INTERVIEW_REQUIRE_DATA_READY"),
        description=(
            "When true, AI interview draft generation requires data-check run status ready. "
            "Enable if product policy demands full data processing before question generation."
        ),
    )

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

    allow_screening_passed_bypass_data_check: bool = Field(
        default=False,
        validation_alias=AliasChoices("ALLOW_SCREENING_PASSED_BYPASS_DATA_CHECK"),
        description=(
            "Break-glass: allow POST /screening/transition screening_passed without data-check run "
            "status ready. Only effective for global admin users. Must stay false in production."
        ),
    )

    @field_validator("database_url")
    @classmethod
    def normalize_db_url(cls, v: str) -> str:
        if v.startswith("postgresql+asyncpg://"):
            return v.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        return v

    @field_validator("upload_root", mode="after")
    @classmethod
    def resolve_upload_root(cls, v: str) -> str:
        p = Path(v).expanduser()
        if p.is_absolute():
            return str(p.resolve())
        return str((_REPO_ROOT / p).resolve())

    @field_validator("storage_read_mode", mode="before")
    @classmethod
    def normalize_storage_read_mode(cls, v: str) -> str:
        return str(v).strip().lower()

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
