import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from invision_api.db.base import Base
from invision_api.models.mixins import UUIDPrimaryKeyMixin


class ApplicationRawSubmissionSnapshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "application_raw_submission_snapshots"
    __table_args__ = (
        UniqueConstraint("application_id", "snapshot_kind", name="uq_raw_snapshot_app_kind"),
        Index("ix_raw_snapshot_application", "application_id"),
        Index("ix_raw_snapshot_created", "created_at"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
