"""Durable, safe synchronization phase diagnostics.

Revision ID: sync_errors_20260803
Revises: maintenance_sync_20260804
"""

from alembic import op
import sqlalchemy as sa


revision = "sync_errors_20260803"
down_revision = "maintenance_sync_20260804"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = (
        sa.Column("phase_key", sa.String(64), nullable=True),
        sa.Column("provider", sa.String(120), nullable=True),
        sa.Column("safe_url", sa.String(1024), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=True),
        sa.Column("checkpoint_offset", sa.Integer(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=True),
    )
    for column in columns:
        op.add_column("sync_job_errors", column)
    op.execute(sa.text("UPDATE sync_job_errors SET first_occurred_at = created_at, last_seen_at = created_at"))
    op.create_index("ix_sync_job_errors_phase_key", "sync_job_errors", ["phase_key"])
    op.create_index("ix_sync_job_errors_http_status", "sync_job_errors", ["http_status"])
    op.create_index("ix_sync_job_errors_retryable", "sync_job_errors", ["retryable"])
    op.create_index("ix_sync_job_errors_last_seen_at", "sync_job_errors", ["last_seen_at"])
    op.create_index("ix_sync_job_errors_fingerprint", "sync_job_errors", ["fingerprint"], unique=True)


def downgrade() -> None:
    for index in (
        "ix_sync_job_errors_fingerprint", "ix_sync_job_errors_last_seen_at",
        "ix_sync_job_errors_retryable", "ix_sync_job_errors_http_status",
        "ix_sync_job_errors_phase_key",
    ):
        op.drop_index(index, table_name="sync_job_errors")
    for column in (
        "fingerprint", "last_seen_at", "first_occurred_at", "occurrence_count",
        "attempt", "checkpoint_offset", "retryable", "http_status", "safe_url",
        "provider", "phase_key",
    ):
        op.drop_column("sync_job_errors", column)
