"""durable knowledge import orchestration

Revision ID: knowledge_workers_20260723
Revises: knowledge_2a1_20260723
Create Date: 2026-07-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "knowledge_workers_20260723"
down_revision = "knowledge_2a1_20260723"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_providers", sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("knowledge_providers", sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("knowledge_providers", sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "knowledge_providers",
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("knowledge_providers", sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE knowledge_providers SET health = CASE "
        "WHEN enabled IS FALSE THEN 'disabled' "
        "WHEN health = 'failed' THEN 'unavailable' "
        "WHEN health NOT IN ('healthy','degraded','unavailable','disabled','unknown') THEN 'unknown' "
        "ELSE health END"
    )
    op.create_check_constraint(
        "ck_knowledge_provider_health",
        "knowledge_providers",
        "health IN ('healthy','degraded','unavailable','disabled','unknown')",
    )
    op.create_check_constraint(
        "ck_knowledge_provider_failures_nonnegative",
        "knowledge_providers",
        "consecutive_failures >= 0",
    )

    op.create_table(
        "knowledge_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("entity_type_id", sa.String(length=64), nullable=True),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("parent_job_id", sa.Uuid(), nullable=True),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("safe_last_error", sa.String(length=512), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("trigger", sa.String(length=24), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("attempt_count >= 0", name="ck_knowledge_job_attempt_count_nonnegative"),
        sa.CheckConstraint("max_attempts > 0", name="ck_knowledge_job_max_attempts_positive"),
        sa.CheckConstraint("parent_job_id IS NULL OR parent_job_id <> id", name="ck_knowledge_job_parent_not_self"),
        sa.CheckConstraint("priority >= 0", name="ck_knowledge_job_priority_nonnegative"),
        sa.CheckConstraint(
            "state IN ('pending','claimed','running','retrying','succeeded','partially_succeeded','failed','cancelled')",
            name="ck_knowledge_job_state",
        ),
        sa.CheckConstraint(
            "trigger IN ('bootstrap','scheduled','manual','retry','renormalize','system')",
            name="ck_knowledge_job_trigger",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["entity_type_id"], ["knowledge_entity_types.entity_type"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_job_id"], ["knowledge_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_id"], ["knowledge_providers.provider_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_jobs_due", "knowledge_jobs", ["state", "priority", "scheduled_at"])
    op.create_index("ix_knowledge_jobs_provider_state", "knowledge_jobs", ["provider_id", "state"])
    op.create_index("ix_knowledge_jobs_entity_state", "knowledge_jobs", ["entity_type_id", "state"])
    op.create_index("ix_knowledge_jobs_worker_lease", "knowledge_jobs", ["worker_id", "lease_expires_at"])
    op.create_index("ix_knowledge_jobs_correlation", "knowledge_jobs", ["correlation_id"])
    op.create_index(
        "uq_knowledge_jobs_active_idempotency",
        "knowledge_jobs",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("state IN ('pending','claimed','running','retrying')"),
    )

    op.create_table(
        "knowledge_job_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("safe_error", sa.String(length=512), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("attempt_number > 0", name="ck_knowledge_attempt_number_positive"),
        sa.CheckConstraint(
            "outcome IN ('running','succeeded','partially_succeeded','retrying','failed','cancelled','lease_expired')",
            name="ck_knowledge_attempt_outcome",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["knowledge_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_knowledge_job_attempt_number"),
    )
    op.create_index("ix_knowledge_attempts_job_created", "knowledge_job_attempts", ["job_id", "created_at"])
    op.create_index("ix_knowledge_attempts_worker_started", "knowledge_job_attempts", ["worker_id", "started_at"])

    op.create_table(
        "knowledge_worker_heartbeats",
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("worker_type", sa.String(length=64), nullable=False, server_default="knowledge"),
        sa.Column("node_id", sa.String(length=128), nullable=False),
        sa.Column("process_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("current_job_id", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(length=24), nullable=False, server_default="idle"),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("safe_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.CheckConstraint(
            "state IN ('idle','running','stopping','offline','error')",
            name="ck_knowledge_worker_state",
        ),
        sa.ForeignKeyConstraint(["current_job_id"], ["knowledge_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("worker_id"),
    )
    op.create_index("ix_knowledge_workers_state_seen", "knowledge_worker_heartbeats", ["state", "last_seen_at"])

    op.create_table(
        "knowledge_provider_cursors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("entity_type_id", sa.String(length=64), nullable=False),
        sa.Column("scope_hash", sa.String(length=64), nullable=False),
        sa.Column("cursor", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_job_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.String(length=128), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["entity_type_id"], ["knowledge_entity_types.entity_type"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_job_id"], ["knowledge_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_id"], ["knowledge_providers.provider_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id", "entity_type_id", "scope_hash", name="uq_knowledge_provider_cursor_scope"),
    )
    op.create_index("ix_knowledge_cursors_provider_updated", "knowledge_provider_cursors", ["provider_id", "updated_at"])

    op.add_column("knowledge_documents", sa.Column("content_identity", sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        "uq_knowledge_documents_content_identity",
        "knowledge_documents",
        ["content_identity"],
    )

    op.execute(
        "INSERT INTO knowledge_providers "
        "(provider_id, provider_name, priority, enabled, version, rate_limit, health, "
        "supports_entities, supports_media, supports_search, consecutive_failures) "
        "VALUES ('reference', 'Reference Adapter', 1000, false, 'stage-2a-2', "
        "'{\"requests\": 1, \"window_seconds\": 1}'::jsonb, 'disabled', "
        "'[\"creature\"]'::jsonb, false, false, 0) "
        "ON CONFLICT (provider_id) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_constraint("uq_knowledge_documents_content_identity", "knowledge_documents", type_="unique")
    op.drop_column("knowledge_documents", "content_identity")
    op.drop_table("knowledge_provider_cursors")
    op.drop_table("knowledge_worker_heartbeats")
    op.drop_table("knowledge_job_attempts")
    op.drop_table("knowledge_jobs")
    op.drop_constraint("ck_knowledge_provider_failures_nonnegative", "knowledge_providers", type_="check")
    op.drop_constraint("ck_knowledge_provider_health", "knowledge_providers", type_="check")
    op.drop_column("knowledge_providers", "cooldown_until")
    op.drop_column("knowledge_providers", "consecutive_failures")
    op.drop_column("knowledge_providers", "last_failure_at")
    op.drop_column("knowledge_providers", "last_success_at")
    op.drop_column("knowledge_providers", "last_attempted_at")
