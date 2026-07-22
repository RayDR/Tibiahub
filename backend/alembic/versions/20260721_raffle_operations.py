"""Add durable raffle scheduler and internal notifications.

Revision ID: raffle_operations_20260721
Revises: automatic_raffle_stage1_20260721
"""
from alembic import op
import sqlalchemy as sa

revision = "raffle_operations_20260721"
down_revision = "automatic_raffle_stage1_20260721"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("raffles", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("raffles", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "raffle_scheduler_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("raffle_id", sa.Integer(), sa.ForeignKey("raffles.id"), nullable=False),
        sa.Column("job_id", sa.String(255), nullable=False),
        sa.Column("worker_id", sa.String(255), nullable=False),
        sa.Column("trigger", sa.String(30), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("failure_code", sa.String(100)),
        sa.Column("failure_summary", sa.Text()),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("job_id", name="uq_raffle_scheduler_job_id"),
    )
    op.create_index("ix_raffle_scheduler_attempts_raffle_id", "raffle_scheduler_attempts", ["raffle_id"])
    op.create_table(
        "raffle_scheduler_state",
        sa.Column("worker_id", sa.String(255), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_poll_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_failure_at", sa.DateTime(timezone=True)),
        sa.Column("last_failure_code", sa.String(100)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "internal_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("guild_name", sa.String(200)),
        sa.Column("raffle_id", sa.Integer(), sa.ForeignKey("raffles.id")),
        sa.Column("notification_type", sa.String(80), nullable=False),
        sa.Column("title_key", sa.String(255), nullable=False),
        sa.Column("message_key", sa.String(255), nullable=False),
        sa.Column("interpolation", sa.JSON(), nullable=False),
        sa.Column("deep_link", sa.String(500)),
        sa.Column("deduplication_key", sa.String(255), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("recipient_user_id", "deduplication_key", name="uq_notification_recipient_dedupe"),
    )
    op.create_index("ix_internal_notifications_recipient_user_id", "internal_notifications", ["recipient_user_id"])
    op.create_index("ix_internal_notifications_raffle_id", "internal_notifications", ["raffle_id"])
    op.create_index("ix_internal_notifications_guild_name", "internal_notifications", ["guild_name"])
    op.create_index("ix_internal_notifications_notification_type", "internal_notifications", ["notification_type"])
    op.create_index("ix_internal_notifications_is_read", "internal_notifications", ["is_read"])


def downgrade() -> None:
    op.drop_table("internal_notifications")
    op.drop_table("raffle_scheduler_state")
    op.drop_table("raffle_scheduler_attempts")
    op.drop_column("raffles", "next_retry_at")
    op.drop_column("raffles", "retry_count")
