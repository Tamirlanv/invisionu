"""link validation results table

Revision ID: 20260401_0004
Revises: 20260331_0003
Create Date: 2026-04-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260401_0004"
down_revision: str | None = "20260331_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "link_validation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=True),
        sa.Column("is_valid_format", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_reachable", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("availability_status", sa.String(length=32), server_default="unknown", nullable=False),
        sa.Column("provider", sa.String(length=32), server_default="unknown", nullable=False),
        sa.Column("resource_type", sa.String(length=32), server_default="unknown", nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("content_length", sa.Integer(), nullable=True),
        sa.Column("redirected", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("redirect_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_link_validation_results_created_at", "link_validation_results", ["created_at"], unique=False)
    op.create_index(
        "ix_link_validation_results_application_id", "link_validation_results", ["application_id"], unique=False
    )
    op.create_index("ix_link_validation_results_provider", "link_validation_results", ["provider"], unique=False)
    op.create_index(
        "ix_link_validation_results_availability", "link_validation_results", ["availability_status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_link_validation_results_availability", table_name="link_validation_results")
    op.drop_index("ix_link_validation_results_provider", table_name="link_validation_results")
    op.drop_index("ix_link_validation_results_application_id", table_name="link_validation_results")
    op.drop_index("ix_link_validation_results_created_at", table_name="link_validation_results")
    op.drop_table("link_validation_results")
