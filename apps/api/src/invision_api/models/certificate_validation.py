import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from invision_api.db.base import Base
from invision_api.models.mixins import UUIDPrimaryKeyMixin


class CertificateValidationResultRow(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "certificate_validation_results"
    __table_args__ = (
        Index("ix_certificate_validation_created_at", "created_at"),
        Index("ix_certificate_validation_application_id", "application_id"),
        Index("ix_certificate_validation_document_type", "document_type"),
        Index("ix_certificate_validation_processing_status", "processing_status"),
    )

    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True
    )
    document_type: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="processing_failed")
    extracted_fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    threshold_checks: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    authenticity_status: Mapped[str] = mapped_column(String(32), nullable=False, default="manual_review_required")
    template_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    fraud_signals: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    explainability: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
