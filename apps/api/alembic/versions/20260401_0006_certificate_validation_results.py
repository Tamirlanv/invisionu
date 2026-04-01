"""certificate validation results table

Revision ID: 20260401_0006
Revises: 20260401_0005
Create Date: 2026-04-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260401_0006"
down_revision: str | None = "20260401_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "certificate_validation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("extracted_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("threshold_checks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("authenticity_status", sa.String(length=32), nullable=False),
        sa.Column("template_match_score", sa.Float(), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("fraud_signals", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("explainability", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_certificate_validation_created_at", "certificate_validation_results", ["created_at"], unique=False)
    op.create_index(
        "ix_certificate_validation_application_id", "certificate_validation_results", ["application_id"], unique=False
    )
    op.create_index(
        "ix_certificate_validation_document_type", "certificate_validation_results", ["document_type"], unique=False
    )
    op.create_index(
        "ix_certificate_validation_processing_status",
        "certificate_validation_results",
        ["processing_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_certificate_validation_processing_status", table_name="certificate_validation_results")
    op.drop_index("ix_certificate_validation_document_type", table_name="certificate_validation_results")
    op.drop_index("ix_certificate_validation_application_id", table_name="certificate_validation_results")
    op.drop_index("ix_certificate_validation_created_at", table_name="certificate_validation_results")
    op.drop_table("certificate_validation_results")
