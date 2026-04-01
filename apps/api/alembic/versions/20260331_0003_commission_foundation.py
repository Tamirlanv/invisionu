"""commission foundation tables

Revision ID: 20260331_0003
Revises: 20250328_0002
Create Date: 2026-03-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260331_0003"
down_revision: str | None = "20250328_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commission_users",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "application_stage_states",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attention_flag_manual", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("application_id", "stage"),
    )
    op.create_index("ix_stage_state_stage_status", "application_stage_states", ["stage", "status"], unique=False)
    op.create_index("ix_stage_state_attention", "application_stage_states", ["attention_flag_manual"], unique=False)
    op.create_index("ix_stage_state_updated", "application_stage_states", ["updated_at"], unique=False)

    op.create_table(
        "application_stage_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason_comment", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_stage_status_hist_app_stage_time",
        "application_stage_status_history",
        ["application_id", "stage", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_application_stage_status_history_application_id",
        "application_stage_status_history",
        ["application_id"],
        unique=False,
    )

    op.create_table(
        "review_rubric_scores",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rubric", sa.String(length=32), nullable=False),
        sa.Column("score", sa.String(length=16), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "reviewer_user_id", "rubric", name="uq_rubric_per_reviewer"),
    )
    op.create_index("ix_rubric_app", "review_rubric_scores", ["application_id"], unique=False)
    op.create_index("ix_rubric_reviewer", "review_rubric_scores", ["reviewer_user_id"], unique=False)

    op.create_table(
        "internal_recommendations",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommendation", sa.String(length=32), nullable=False),
        sa.Column("reason_comment", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "reviewer_user_id", name="uq_internal_rec_per_reviewer"),
    )
    op.create_index("ix_internal_rec_app", "internal_recommendations", ["application_id"], unique=False)
    op.create_index("ix_internal_rec_reviewer", "internal_recommendations", ["reviewer_user_id"], unique=False)

    op.create_table(
        "comment_tags",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_comment_tag_key"),
    )

    op.create_table(
        "application_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_app_comments_app_time", "application_comments", ["application_id", "created_at"], unique=False)
    op.create_index("ix_application_comments_application_id", "application_comments", ["application_id"], unique=False)

    op.create_table(
        "application_comment_tags",
        sa.Column("comment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["comment_id"], ["application_comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["comment_tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("comment_id", "tag_id"),
        sa.UniqueConstraint("comment_id", "tag_id", name="uq_comment_tag_link"),
    )

    op.create_table(
        "application_tags",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_application_tag_key"),
    )

    op.create_table(
        "application_application_tags",
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["application_tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("application_id", "tag_id"),
        sa.UniqueConstraint("application_id", "tag_id", name="uq_app_tag_link"),
    )
    op.create_index("ix_app_tag_app", "application_application_tags", ["application_id"], unique=False)
    op.create_index("ix_app_tag_tag", "application_application_tags", ["tag_id"], unique=False)

    op.create_table(
        "application_commission_projections",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_full_name", sa.String(length=255), server_default="", nullable=False),
        sa.Column("program", sa.String(length=128), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_stage", sa.String(length=64), nullable=False),
        sa.Column("current_stage_status", sa.String(length=32), nullable=True),
        sa.Column("attention_flag_manual", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("final_decision", sa.String(length=64), nullable=True),
        sa.Column("has_ai_summary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ai_recommendation", sa.String(length=32), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("application_id"),
    )
    op.create_index("ix_comm_proj_stage", "application_commission_projections", ["current_stage"], unique=False)
    op.create_index(
        "ix_comm_proj_stage_status", "application_commission_projections", ["current_stage_status"], unique=False
    )
    op.create_index("ix_comm_proj_program", "application_commission_projections", ["program"], unique=False)
    op.create_index("ix_comm_proj_city", "application_commission_projections", ["city"], unique=False)
    op.create_index("ix_comm_proj_submitted", "application_commission_projections", ["submitted_at"], unique=False)
    op.create_index("ix_comm_proj_updated", "application_commission_projections", ["updated_at"], unique=False)

    op.create_table(
        "export_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("filter_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("application_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_storage_key", sa.String(length=512), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_export_jobs_status_created", "export_jobs", ["status", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_export_jobs_status_created", table_name="export_jobs")
    op.drop_table("export_jobs")

    op.drop_index("ix_comm_proj_updated", table_name="application_commission_projections")
    op.drop_index("ix_comm_proj_submitted", table_name="application_commission_projections")
    op.drop_index("ix_comm_proj_city", table_name="application_commission_projections")
    op.drop_index("ix_comm_proj_program", table_name="application_commission_projections")
    op.drop_index("ix_comm_proj_stage_status", table_name="application_commission_projections")
    op.drop_index("ix_comm_proj_stage", table_name="application_commission_projections")
    op.drop_table("application_commission_projections")

    op.drop_index("ix_app_tag_tag", table_name="application_application_tags")
    op.drop_index("ix_app_tag_app", table_name="application_application_tags")
    op.drop_table("application_application_tags")
    op.drop_table("application_tags")

    op.drop_table("application_comment_tags")
    op.drop_index("ix_application_comments_application_id", table_name="application_comments")
    op.drop_index("ix_app_comments_app_time", table_name="application_comments")
    op.drop_table("application_comments")
    op.drop_table("comment_tags")

    op.drop_index("ix_internal_rec_reviewer", table_name="internal_recommendations")
    op.drop_index("ix_internal_rec_app", table_name="internal_recommendations")
    op.drop_table("internal_recommendations")

    op.drop_index("ix_rubric_reviewer", table_name="review_rubric_scores")
    op.drop_index("ix_rubric_app", table_name="review_rubric_scores")
    op.drop_table("review_rubric_scores")

    op.drop_index(
        "ix_application_stage_status_history_application_id",
        table_name="application_stage_status_history",
    )
    op.drop_index(
        "ix_stage_status_hist_app_stage_time",
        table_name="application_stage_status_history",
    )
    op.drop_table("application_stage_status_history")

    op.drop_index("ix_stage_state_updated", table_name="application_stage_states")
    op.drop_index("ix_stage_state_attention", table_name="application_stage_states")
    op.drop_index("ix_stage_state_stage_status", table_name="application_stage_states")
    op.drop_table("application_stage_states")

    op.drop_table("commission_users")

