"""candidate validation orchestration tables

Revision ID: 20260401_0007
Revises: 20260401_0006
Create Date: 2026-04-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260401_0007"
down_revision: str | None = "20260401_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_validation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("overall_status", sa.String(length=32), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("explainability", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidate_validation_runs_application_id", "candidate_validation_runs", ["application_id"], unique=False)
    op.create_index("ix_candidate_validation_runs_overall_status", "candidate_validation_runs", ["overall_status"], unique=False)
    op.create_index("ix_candidate_validation_runs_updated_at", "candidate_validation_runs", ["updated_at"], unique=False)

    op.create_table(
        "candidate_validation_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("check_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["candidate_validation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidate_validation_checks_run_id", "candidate_validation_checks", ["run_id"], unique=False)
    op.create_index(
        "ix_candidate_validation_checks_type_status",
        "candidate_validation_checks",
        ["check_type", "status"],
        unique=False,
    )

    op.create_table(
        "candidate_validation_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("check_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["check_id"], ["candidate_validation_checks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["candidate_validation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidate_validation_audit_events_run_id",
        "candidate_validation_audit_events",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_validation_audit_events_run_id", table_name="candidate_validation_audit_events")
    op.drop_table("candidate_validation_audit_events")
    op.drop_index("ix_candidate_validation_checks_type_status", table_name="candidate_validation_checks")
    op.drop_index("ix_candidate_validation_checks_run_id", table_name="candidate_validation_checks")
    op.drop_table("candidate_validation_checks")
    op.drop_index("ix_candidate_validation_runs_updated_at", table_name="candidate_validation_runs")
    op.drop_index("ix_candidate_validation_runs_overall_status", table_name="candidate_validation_runs")
    op.drop_index("ix_candidate_validation_runs_application_id", table_name="candidate_validation_runs")
    op.drop_table("candidate_validation_runs")
