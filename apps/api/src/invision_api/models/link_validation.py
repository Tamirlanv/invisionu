import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from invision_api.db.base import Base
from invision_api.models.mixins import UUIDPrimaryKeyMixin


class LinkValidationResultRow(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "link_validation_results"
    __table_args__ = (
        Index("ix_link_validation_results_created_at", "created_at"),
        Index("ix_link_validation_results_application_id", "application_id"),
        Index("ix_link_validation_results_provider", "provider"),
        Index("ix_link_validation_results_availability", "availability_status"),
    )

    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True
    )
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_valid_format: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_reachable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    availability_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    redirected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    redirect_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
