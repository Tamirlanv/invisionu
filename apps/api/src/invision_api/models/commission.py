import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from invision_api.db.base import Base
from invision_api.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CommissionUser(Base, TimestampMixin):
    """Per-committee RBAC role. Global RoleName.committee/admin gates access."""

    __tablename__ = "commission_users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # viewer|reviewer|admin


class ApplicationStageState(Base, TimestampMixin):
    """Stage-local review status and flags (separate from final decision)."""

    __tablename__ = "application_stage_states"
    __table_args__ = (
        Index("ix_stage_state_stage_status", "stage", "status"),
        Index("ix_stage_state_attention", "attention_flag_manual"),
        Index("ix_stage_state_updated", "updated_at"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # new|in_review|needs_attention|approved|rejected
    attention_flag_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ApplicationStageStatusHistory(Base, UUIDPrimaryKeyMixin):
    """Immutable history for stage status changes (for audit trail)."""

    __tablename__ = "application_stage_status_history"
    __table_args__ = (
        Index("ix_stage_status_hist_app_stage_time", "application_id", "stage", "created_at"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class ReviewRubricScore(Base, TimestampMixin):
    """Per-reviewer rubric scores; one row per rubric item."""

    __tablename__ = "review_rubric_scores"
    __table_args__ = (
        UniqueConstraint("application_id", "reviewer_user_id", "rubric", name="uq_rubric_per_reviewer"),
        Index("ix_rubric_app", "application_id"),
        Index("ix_rubric_reviewer", "reviewer_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rubric: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[str] = mapped_column(String(16), nullable=False)  # strong|medium|low
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class SectionReviewScore(Base, TimestampMixin):
    """Per-reviewer numeric scores for each tab section (1-5 scale).

    Stores both platform-recommended and manual override scores.
    """

    __tablename__ = "section_review_scores"
    __table_args__ = (
        UniqueConstraint(
            "application_id", "reviewer_user_id", "section", "score_key",
            name="uq_section_score",
        ),
        Index("ix_section_score_app", "application_id"),
        Index("ix_section_score_reviewer", "reviewer_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    section: Mapped[str] = mapped_column(String(32), nullable=False)
    score_key: Mapped[str] = mapped_column(String(64), nullable=False)
    recommended_score: Mapped[int] = mapped_column(Integer, nullable=False)
    manual_score: Mapped[int | None] = mapped_column(Integer, nullable=True)


class InternalRecommendationRow(Base, TimestampMixin):
    """Per-reviewer internal recommendation within commission (not final decision)."""

    __tablename__ = "internal_recommendations"
    __table_args__ = (
        UniqueConstraint("application_id", "reviewer_user_id", name="uq_internal_rec_per_reviewer"),
        Index("ix_internal_rec_app", "application_id"),
        Index("ix_internal_rec_reviewer", "reviewer_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    recommendation: Mapped[str] = mapped_column(String(32), nullable=False)  # recommend_forward|needs_discussion|reject
    reason_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ApplicationComment(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "application_comments"
    __table_args__ = (Index("ix_app_comments_app_time", "application_id", "created_at"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    tags: Mapped[list["CommentTag"]] = relationship(
        secondary="application_comment_tags",
        back_populates="comments",
        lazy="selectin",
    )


class CommentTag(Base, TimestampMixin):
    __tablename__ = "comment_tags"
    __table_args__ = (UniqueConstraint("key", name="uq_comment_tag_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(64), nullable=False)

    comments: Mapped[list[ApplicationComment]] = relationship(
        secondary="application_comment_tags",
        back_populates="tags",
        lazy="selectin",
    )


class ApplicationCommentTag(Base):
    __tablename__ = "application_comment_tags"
    __table_args__ = (UniqueConstraint("comment_id", "tag_id", name="uq_comment_tag_link"),)

    comment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("application_comments.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comment_tags.id", ondelete="CASCADE"), primary_key=True
    )


class ApplicationTag(Base, TimestampMixin):
    __tablename__ = "application_tags"
    __table_args__ = (UniqueConstraint("key", name="uq_application_tag_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(64), nullable=False)


class ApplicationTagLink(Base):
    __tablename__ = "application_application_tags"
    __table_args__ = (
        UniqueConstraint("application_id", "tag_id", name="uq_app_tag_link"),
        Index("ix_app_tag_app", "application_id"),
        Index("ix_app_tag_tag", "tag_id"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("application_tags.id", ondelete="CASCADE"), primary_key=True
    )


class ApplicationCommissionProjection(Base, TimestampMixin):
    """Denormalized read-model for kanban/search. Updated by projection service."""

    __tablename__ = "application_commission_projections"
    __table_args__ = (
        Index("ix_comm_proj_stage", "current_stage"),
        Index("ix_comm_proj_stage_status", "current_stage_status"),
        Index("ix_comm_proj_program", "program"),
        Index("ix_comm_proj_city", "city"),
        Index("ix_comm_proj_submitted", "submitted_at"),
        Index("ix_comm_proj_updated", "updated_at"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True
    )
    candidate_full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    program: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    current_stage_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    attention_flag_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    final_decision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    has_ai_summary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_recommendation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ExportJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "export_jobs"
    __table_args__ = (Index("ix_export_jobs_status_created", "status", "created_at"),)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    format: Mapped[str] = mapped_column(String(16), nullable=False)  # csv|xlsx
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    filter_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    application_ids: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    result_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

