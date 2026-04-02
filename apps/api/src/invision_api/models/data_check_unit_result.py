import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from invision_api.db.base import Base
from invision_api.models.mixins import UUIDPrimaryKeyMixin


class DataCheckUnitResult(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "data_check_unit_results"
    __table_args__ = (
        UniqueConstraint("run_id", "unit_type", name="uq_data_check_unit_run_type"),
        Index("ix_data_check_unit_application", "application_id"),
        Index("ix_data_check_unit_status", "status"),
        Index("ix_data_check_unit_type_status", "unit_type", "status"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_validation_runs.id", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    unit_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    explainability: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    manual_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"), nullable=False
    )
