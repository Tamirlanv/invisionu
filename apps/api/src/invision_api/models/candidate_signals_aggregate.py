import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from invision_api.db.base import Base
from invision_api.models.mixins import UUIDPrimaryKeyMixin


class CandidateSignalsAggregate(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "candidate_signals_aggregates"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_candidate_signals_run"),
        UniqueConstraint("application_id", name="uq_candidate_signals_application"),
        Index("ix_candidate_signals_application", "application_id"),
        Index("ix_candidate_signals_review_status", "review_readiness_status"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_validation_runs.id", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    leadership_signals: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    initiative_signals: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    resilience_signals: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    responsibility_signals: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    growth_signals: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    mission_fit_signals: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    strong_motivation_signals: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    communication_signals: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    attention_flags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    authenticity_concern_signals: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    review_readiness_status: Mapped[str] = mapped_column(String(32), nullable=False, default="partial_processing_ready")
    manual_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    explainability: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()"), nullable=False
    )
