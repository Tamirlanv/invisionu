"""section review scores

Revision ID: 20260402_0009
Revises: 20260402_0008
Create Date: 2026-04-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260402_0009"
down_revision: str | None = "20260402_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "section_review_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section", sa.String(length=32), nullable=False),
        sa.Column("score_key", sa.String(length=64), nullable=False),
        sa.Column("recommended_score", sa.Integer(), nullable=False),
        sa.Column("manual_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "application_id", "reviewer_user_id", "section", "score_key",
            name="uq_section_score",
        ),
    )
    op.create_index("ix_section_score_app", "section_review_scores", ["application_id"])
    op.create_index("ix_section_score_reviewer", "section_review_scores", ["reviewer_user_id"])


def downgrade() -> None:
    op.drop_index("ix_section_score_reviewer", table_name="section_review_scores")
    op.drop_index("ix_section_score_app", table_name="section_review_scores")
    op.drop_table("section_review_scores")
