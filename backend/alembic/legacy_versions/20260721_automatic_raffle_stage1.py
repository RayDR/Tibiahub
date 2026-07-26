"""Add automatic guild raffle stage-one foundations.

Revision ID: automatic_raffle_stage1_20260721
Revises: product_polish_20260720
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa


revision = "automatic_raffle_stage1_20260721"
down_revision = "product_polish_20260720"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _add_missing(table: str, columns: list[sa.Column]) -> None:
    existing = _columns(table)
    for column in columns:
        if column.name not in existing:
            op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    published_by_column = (
        sa.Column("published_by_id", sa.Integer())
        if bind.dialect.name == "sqlite"
        else sa.Column("published_by_id", sa.Integer(), sa.ForeignKey("users.id"))
    )
    _add_missing("users", [sa.Column("last_app_login_at", sa.DateTime(timezone=True))])
    _add_missing("raffles", [
        sa.Column("purpose", sa.String(20), nullable=False, server_default="legacy"),
        sa.Column("timezone_name", sa.String(64), nullable=False, server_default="America/Chicago"),
        sa.Column("eligibility_days", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("eligibility_cutoff_at", sa.DateTime(timezone=True)),
        sa.Column("publication_status", sa.String(20), nullable=False, server_default="private"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        published_by_column,
        sa.Column("execution_state", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column("execution_trigger", sa.String(20)),
        sa.Column("scheduler_job_id", sa.String(255)),
        sa.Column("claim_token", sa.String(64)),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(100)),
        sa.Column("last_error_summary", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    ])
    _add_missing("raffle_prizes", [
        sa.Column("position", sa.String(20)),
        sa.Column("amount", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(20)),
    ])

    if "raffle_manager_grants" not in tables:
        op.create_table("raffle_manager_grants",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("raffle_id", sa.Integer(), sa.ForeignKey("raffles.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("granted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("revoked_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("raffle_id", "user_id", name="uq_raffle_manager_grant"),
        )
        op.create_index("ix_raffle_manager_grants_raffle_id", "raffle_manager_grants", ["raffle_id"])
        op.create_index("ix_raffle_manager_grants_user_id", "raffle_manager_grants", ["user_id"])

    if "raffle_eligibility_snapshots" not in tables:
        op.create_table("raffle_eligibility_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("raffle_id", sa.Integer(), sa.ForeignKey("raffles.id"), nullable=False),
            sa.Column("snapshot_number", sa.Integer(), nullable=False),
            sa.Column("cutoff_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("timezone_name", sa.String(64), nullable=False),
            sa.Column("eligibility_days", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(50), nullable=False),
            sa.Column("candidate_count", sa.Integer(), nullable=False),
            sa.Column("eligible_count", sa.Integer(), nullable=False),
            sa.Column("excluded_count", sa.Integer(), nullable=False),
            sa.Column("snapshot_hash", sa.String(64), nullable=False),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("raffle_id", "snapshot_number", name="uq_raffle_snapshot_number"),
        )
        op.create_index("ix_raffle_eligibility_snapshots_raffle_id", "raffle_eligibility_snapshots", ["raffle_id"])

    if "raffle_eligibility_entries" not in tables:
        op.create_table("raffle_eligibility_entries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("raffle_eligibility_snapshots.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("character_name", sa.String(100)),
            sa.Column("guild_name", sa.String(200)),
            sa.Column("guild_rank", sa.String(100)),
            sa.Column("last_activity_at", sa.DateTime(timezone=True)),
            sa.Column("is_eligible", sa.Boolean(), nullable=False),
            sa.Column("exclusion_code", sa.String(50)),
            sa.Column("exclusion_summary", sa.String(255)),
            sa.Column("source_data", sa.JSON()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("snapshot_id", "user_id", name="uq_raffle_snapshot_user"),
        )
        op.create_index("ix_raffle_eligibility_entries_snapshot_id", "raffle_eligibility_entries", ["snapshot_id"])

    if "raffle_runs" not in tables:
        op.create_table("raffle_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("raffle_id", sa.Integer(), sa.ForeignKey("raffles.id"), nullable=False),
            sa.Column("run_number", sa.Integer(), nullable=False),
            sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("raffle_eligibility_snapshots.id"), nullable=False),
            sa.Column("parent_run_id", sa.Integer(), sa.ForeignKey("raffle_runs.id")),
            sa.Column("trigger", sa.String(20), nullable=False),
            sa.Column("state", sa.String(20), nullable=False),
            sa.Column("requested_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True)),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
            sa.Column("failure_code", sa.String(100)),
            sa.Column("failure_summary", sa.Text()),
            sa.Column("algorithm_version", sa.String(50), nullable=False),
            sa.Column("entropy_commitment", sa.String(64)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("raffle_id", "run_number", name="uq_raffle_run_number"),
        )
        op.create_index("ix_raffle_runs_raffle_id", "raffle_runs", ["raffle_id"])

    if "raffle_run_results" not in tables:
        op.create_table("raffle_run_results",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("run_id", sa.Integer(), sa.ForeignKey("raffle_runs.id"), nullable=False),
            sa.Column("prize_id", sa.Integer(), sa.ForeignKey("raffle_prizes.id"), nullable=False),
            sa.Column("prize_position", sa.String(20), nullable=False),
            sa.Column("participant_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("participant_character_name", sa.String(100), nullable=False),
            sa.Column("selection_index", sa.Integer(), nullable=False),
            sa.Column("candidate_count", sa.Integer(), nullable=False),
            sa.Column("derived_entropy_hash", sa.String(64), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("superseded_by_result_id", sa.Integer(), sa.ForeignKey("raffle_run_results.id")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("run_id", "prize_position", name="uq_raffle_run_position"),
        )
        op.create_index("ix_raffle_run_results_run_id", "raffle_run_results", ["run_id"])
        op.create_index("ix_raffle_run_results_is_active", "raffle_run_results", ["is_active"])

    if "raffle_prize_deliveries" not in tables:
        op.create_table("raffle_prize_deliveries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("raffle_id", sa.Integer(), sa.ForeignKey("raffles.id"), nullable=False),
            sa.Column("result_id", sa.Integer(), sa.ForeignKey("raffle_run_results.id"), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("delivery_deadline_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("delivered_at", sa.DateTime(timezone=True)),
            sa.Column("delivered_by_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("note", sa.Text()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("result_id", name="uq_raffle_delivery_result"),
        )
        op.create_index("ix_raffle_prize_deliveries_raffle_id", "raffle_prize_deliveries", ["raffle_id"])

    if "raffle_rerun_audits" not in tables:
        op.create_table("raffle_rerun_audits",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("raffle_id", sa.Integer(), sa.ForeignKey("raffles.id"), nullable=False),
            sa.Column("source_run_id", sa.Integer(), sa.ForeignKey("raffle_runs.id"), nullable=False),
            sa.Column("new_run_id", sa.Integer(), sa.ForeignKey("raffle_runs.id"), nullable=False),
            sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("positions", sa.JSON(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("override_delivered", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("override_reason", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_raffle_rerun_audits_raffle_id", "raffle_rerun_audits", ["raffle_id"])


def downgrade() -> None:
    # Deliberately non-destructive. Roll back using a reviewed backup/migration.
    pass
