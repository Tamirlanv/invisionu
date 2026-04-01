"""video validation results table

Revision ID: 20260401_0005
Revises: 20260401_0004
Create Date: 2026-04-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260401_0005"
down_revision: str | None = "20260401_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_validation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("video_url", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=True),
        sa.Column("access_status", sa.String(length=32), nullable=False),
        sa.Column("media_status", sa.String(length=32), nullable=False),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("has_video_track", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_audio_track", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("codec_video", sa.String(length=128), nullable=True),
        sa.Column("codec_audio", sa.String(length=128), nullable=True),
        sa.Column("total_frames_analyzed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("face_detected_frames_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("face_coverage_ratio", sa.Float(), server_default="0", nullable=False),
        sa.Column("average_face_confidence", sa.Float(), nullable=True),
        sa.Column("sampled_timestamps_sec", postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column("has_speech", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("speech_segment_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("speech_coverage_ratio", sa.Float(), nullable=True),
        sa.Column("transcript_preview", sa.Text(), nullable=True),
        sa.Column("transcript_confidence", sa.Float(), nullable=True),
        sa.Column("likely_face_visible", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("likely_speech_audible", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("likely_presentation_valid", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("manual_review_required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("explainability", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_video_validation_created_at", "video_validation_results", ["created_at"], unique=False)
    op.create_index(
        "ix_video_validation_application_id", "video_validation_results", ["application_id"], unique=False
    )
    op.create_index(
        "ix_video_validation_access_status", "video_validation_results", ["access_status"], unique=False
    )
    op.create_index("ix_video_validation_media_status", "video_validation_results", ["media_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_video_validation_media_status", table_name="video_validation_results")
    op.drop_index("ix_video_validation_access_status", table_name="video_validation_results")
    op.drop_index("ix_video_validation_application_id", table_name="video_validation_results")
    op.drop_index("ix_video_validation_created_at", table_name="video_validation_results")
    op.drop_table("video_validation_results")
