"""data check pipeline tables

Revision ID: 20260402_0008
Revises: 20260401_0007
Create Date: 2026-04-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260402_0008"
down_revision: str | None = "20260401_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_raw_submission_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_kind", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "snapshot_kind", name="uq_raw_snapshot_app_kind"),
    )
    op.create_index(
        "ix_raw_snapshot_application",
        "application_raw_submission_snapshots",
        ["application_id"],
        unique=False,
    )
    op.create_index("ix_raw_snapshot_created", "application_raw_submission_snapshots", ["created_at"], unique=False)

    op.create_table(
        "data_check_unit_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("explainability", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("manual_review_required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["candidate_validation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "unit_type", name="uq_data_check_unit_run_type"),
    )
    op.create_index("ix_data_check_unit_application", "data_check_unit_results", ["application_id"], unique=False)
    op.create_index("ix_data_check_unit_status", "data_check_unit_results", ["status"], unique=False)
    op.create_index("ix_data_check_unit_type_status", "data_check_unit_results", ["unit_type", "status"], unique=False)

    op.create_table(
        "candidate_signals_aggregates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("leadership_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("initiative_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resilience_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("responsibility_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("growth_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("mission_fit_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("strong_motivation_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("communication_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attention_flags", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("authenticity_concern_signals", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("review_readiness_status", sa.String(length=32), nullable=False),
        sa.Column("manual_review_required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("explainability", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["candidate_validation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_candidate_signals_application"),
        sa.UniqueConstraint("run_id", name="uq_candidate_signals_run"),
    )
    op.create_index("ix_candidate_signals_application", "candidate_signals_aggregates", ["application_id"], unique=False)
    op.create_index(
        "ix_candidate_signals_review_status",
        "candidate_signals_aggregates",
        ["review_readiness_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_signals_review_status", table_name="candidate_signals_aggregates")
    op.drop_index("ix_candidate_signals_application", table_name="candidate_signals_aggregates")
    op.drop_table("candidate_signals_aggregates")

    op.drop_index("ix_data_check_unit_type_status", table_name="data_check_unit_results")
    op.drop_index("ix_data_check_unit_status", table_name="data_check_unit_results")
    op.drop_index("ix_data_check_unit_application", table_name="data_check_unit_results")
    op.drop_table("data_check_unit_results")

    op.drop_index("ix_raw_snapshot_created", table_name="application_raw_submission_snapshots")
    op.drop_index("ix_raw_snapshot_application", table_name="application_raw_submission_snapshots")
    op.drop_table("application_raw_submission_snapshots")
