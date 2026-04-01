import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from invision_api.db.base import Base
from invision_api.models.mixins import UUIDPrimaryKeyMixin


class VideoValidationResultRow(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "video_validation_results"
    __table_args__ = (
        Index("ix_video_validation_created_at", "created_at"),
        Index("ix_video_validation_application_id", "application_id"),
        Index("ix_video_validation_access_status", "access_status"),
        Index("ix_video_validation_media_status", "media_status"),
    )

    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True
    )
    video_url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_status: Mapped[str] = mapped_column(String(32), nullable=False, default="invalid")
    media_status: Mapped[str] = mapped_column(String(32), nullable=False, default="processing_failed")
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_video_track: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_audio_track: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    codec_video: Mapped[str | None] = mapped_column(String(128), nullable=True)
    codec_audio: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total_frames_analyzed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    face_detected_frames_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    face_coverage_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    average_face_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    sampled_timestamps_sec: Mapped[list[float]] = mapped_column(ARRAY(Float), nullable=False, default=list)
    has_speech: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    speech_segment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    speech_coverage_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    transcript_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    likely_face_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    likely_speech_audible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    likely_presentation_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    manual_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    explainability: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
