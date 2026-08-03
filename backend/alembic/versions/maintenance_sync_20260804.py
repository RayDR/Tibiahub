"""Durable maintenance holds, raffle assistance, and full-sync worker.

Revision ID: maintenance_sync_20260804
Revises: account_identity_20260803
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "maintenance_sync_20260804"
down_revision = "account_identity_20260803"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in (
        sa.Column("force_refresh", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("skip_images", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("include_knowledge", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("include_guild_rosters", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("continue_on_error", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("maintenance_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("operation_label", sa.String(255), nullable=True),
        sa.Column("worker_id", sa.String(128), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminal_reason", sa.String(255), nullable=True),
    ):
        op.add_column("sync_jobs", column)
    op.create_index("ix_sync_jobs_worker_id", "sync_jobs", ["worker_id"])
    op.create_index("ix_sync_jobs_lease_expires_at", "sync_jobs", ["lease_expires_at"])
    op.create_index("ix_sync_jobs_next_retry_at", "sync_jobs", ["next_retry_at"])
    op.create_index(
        "uq_sync_jobs_one_active_full", "sync_jobs", ["job_type"], unique=True,
        postgresql_where=sa.text("job_type = 'full' AND status IN ('pending','running')"),
    )
    op.add_column("sync_job_errors", sa.Column("error_category", sa.String(80), nullable=True))

    op.create_table(
        "sync_job_phases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(64), sa.ForeignKey("sync_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phase_key", sa.String(64), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(80), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_entity", sa.String(255), nullable=True),
        sa.Column("current_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checkpoint", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("error_category", sa.String(80), nullable=True),
        sa.Column("safe_error", sa.String(500), nullable=True),
        sa.Column("safe_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("status IN ('pending','running','retrying','completed','failed','skipped','cancelled')", name="ck_sync_job_phase_status"),
        sa.UniqueConstraint("job_id", "phase_key", name="uq_sync_job_phase"),
    )
    op.create_index("ix_sync_job_phases_job_id", "sync_job_phases", ["job_id"])
    op.create_index("ix_sync_job_phases_status", "sync_job_phases", ["status"])
    op.create_index("ix_sync_job_phases_order", "sync_job_phases", ["job_id", "order_index"])
    op.execute(sa.text("""
        INSERT INTO sync_job_phases
            (job_id, phase_key, order_index, provider, required, status, attempt_count,
             max_attempts, processed_count, failed_count, current_offset, checkpoint,
             updated_at, safe_metadata)
        SELECT j.id, plan.phase_key, plan.order_index, plan.provider, false,
               CASE j.status
                   WHEN 'completed' THEN 'completed'
                   WHEN 'failed' THEN 'failed'
                   WHEN 'cancelled' THEN 'cancelled'
                   ELSE 'pending'
               END,
               0, GREATEST(1, COALESCE(j.max_retries, 3) + 1),
               COALESCE(j.processed_count, 0), COALESCE(j.failed_count, 0),
               COALESCE(j.current_offset, 0), COALESCE(j.checkpoint, '{}'::jsonb),
               now(), '{}'::jsonb
        FROM sync_jobs AS j
        CROSS JOIN (VALUES
            ('creatures', 0, 'tibiawiki'), ('bosses', 1, 'tibiawiki'),
            ('items', 2, 'tibiawiki'), ('quests', 3, 'tibiawiki'),
            ('hunt-zones', 4, 'tibiamaps'), ('images', 5, 'resources')
        ) AS plan(phase_key, order_index, provider)
        WHERE j.job_type = 'full'
          AND (plan.phase_key <> 'images' OR j.skip_images IS FALSE)
        UNION ALL
        SELECT j.id, j.job_type, 0, 'legacy', false,
               CASE j.status
                   WHEN 'completed' THEN 'completed'
                   WHEN 'failed' THEN 'failed'
                   WHEN 'cancelled' THEN 'cancelled'
                   ELSE 'pending'
               END,
               0, GREATEST(1, COALESCE(j.max_retries, 3) + 1),
               COALESCE(j.processed_count, 0), COALESCE(j.failed_count, 0),
               COALESCE(j.current_offset, 0), COALESCE(j.checkpoint, '{}'::jsonb),
               now(), '{}'::jsonb
        FROM sync_jobs AS j
        WHERE j.job_type <> 'full'
    """))

    op.create_table(
        "sync_worker_heartbeats",
        sa.Column("worker_id", sa.String(128), primary_key=True),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_job_id", sa.String(64), sa.ForeignKey("sync_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_category", sa.String(80), nullable=True),
    )

    op.create_table(
        "maintenance_holds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hold_type", sa.String(20), nullable=False),
        sa.Column("owner_job_id", sa.String(64), sa.ForeignKey("sync_jobs.id", ondelete="CASCADE"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("public_message", sa.String(500), nullable=False),
        sa.Column("enabled_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("planned_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_release", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("release_reason", sa.Text(), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("hold_type IN ('manual','sync')", name="ck_maintenance_hold_type"),
        sa.CheckConstraint("hold_type <> 'sync' OR owner_job_id IS NOT NULL", name="ck_sync_hold_has_owner"),
        sa.UniqueConstraint("owner_job_id", name="uq_maintenance_sync_owner_job"),
    )
    op.create_index("ix_maintenance_holds_hold_type", "maintenance_holds", ["hold_type"])
    op.create_index("ix_maintenance_holds_owner_job_id", "maintenance_holds", ["owner_job_id"])
    op.create_index("ix_maintenance_holds_active", "maintenance_holds", ["released_at", "hold_type"])

    op.add_column("raffle_eligibility_snapshots", sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("raffle_eligibility_snapshots", sa.Column("invalidated_by_id", sa.Integer(), nullable=True))
    op.add_column("raffle_eligibility_snapshots", sa.Column("invalidation_reason", sa.Text(), nullable=True))
    op.create_foreign_key("fk_raffle_snapshot_invalidated_by", "raffle_eligibility_snapshots", "users", ["invalidated_by_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_raffle_snapshot_invalidated_by", "raffle_eligibility_snapshots", type_="foreignkey")
    for column in ("invalidation_reason", "invalidated_by_id", "invalidated_at"):
        op.drop_column("raffle_eligibility_snapshots", column)
    op.drop_table("maintenance_holds")
    op.drop_table("sync_worker_heartbeats")
    op.drop_table("sync_job_phases")
    op.drop_column("sync_job_errors", "error_category")
    for index in ("ix_sync_jobs_next_retry_at", "ix_sync_jobs_lease_expires_at", "ix_sync_jobs_worker_id"):
        op.drop_index(index, table_name="sync_jobs")
    op.drop_index("uq_sync_jobs_one_active_full", table_name="sync_jobs")
    for column in (
        "terminal_reason", "next_retry_at", "lease_expires_at", "claimed_at", "worker_id",
        "operation_label", "maintenance_requested", "continue_on_error", "include_guild_rosters",
        "include_knowledge", "skip_images", "force_refresh",
    ):
        op.drop_column("sync_jobs", column)
