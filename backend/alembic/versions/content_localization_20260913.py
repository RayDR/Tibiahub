"""Add durable localized content, translation queue, and review metadata.

Revision ID: content_localization_20260913
Revises: creature_semantics_20260912
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "content_localization_20260913"
down_revision = "creature_semantics_20260912"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_localizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_uuid", sa.Uuid(), nullable=True),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_key", sa.String(length=255), nullable=False),
        sa.Column("field_path", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_language", sa.String(length=32), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("source_text_hash", sa.String(length=64), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False, server_default="machine"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="generated"),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("provider_model", sa.String(length=128), nullable=True),
        sa.Column("provider_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('generated','reviewed','approved','stale','failed')",
            name="ck_knowledge_localization_status",
        ),
        sa.CheckConstraint(
            "origin IN ('provider','machine','human')",
            name="ck_knowledge_localization_origin",
        ),
        sa.ForeignKeyConstraint(["entity_uuid"], ["knowledge_entities.uuid"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "resource_type", "resource_key", "field_path", "language",
            name="uq_knowledge_localization_resource_field_language",
        ),
    )
    op.create_index("ix_knowledge_localizations_entity_language", "knowledge_localizations", ["entity_uuid", "language"])
    op.create_index("ix_knowledge_localizations_resource_language", "knowledge_localizations", ["resource_type", "resource_key", "language"])
    op.create_index("ix_knowledge_localizations_review", "knowledge_localizations", ["status", "language", "updated_at"])
    op.create_index("ix_knowledge_localizations_source_hash", "knowledge_localizations", ["source_text_hash"])

    op.create_table(
        "localization_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_uuid", sa.Uuid(), nullable=True),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_key", sa.String(length=255), nullable=False),
        sa.Column("field_path", sa.String(length=255), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("source_text_hash", sa.String(length=64), nullable=False),
        sa.Column("source_language", sa.String(length=32), nullable=False),
        sa.Column("target_language", sa.String(length=32), nullable=False),
        sa.Column("protected_terms", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("context", sa.String(length=512), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(length=100), nullable=True),
        sa.Column("safe_failure_category", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','processing','retry','succeeded','failed','cancelled')",
            name="ck_localization_job_status",
        ),
        sa.ForeignKeyConstraint(["entity_uuid"], ["knowledge_entities.uuid"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_localization_jobs_entity_uuid", "localization_jobs", ["entity_uuid"])
    op.create_index("ix_localization_jobs_status", "localization_jobs", ["status"])
    op.create_index("ix_localization_jobs_next_attempt_at", "localization_jobs", ["next_attempt_at"])
    op.create_index("ix_localization_jobs_due", "localization_jobs", ["status", "next_attempt_at", "id"])
    op.create_index("ix_localization_jobs_resource", "localization_jobs", ["resource_type", "resource_key", "target_language"])

    op.create_table(
        "localization_worker_heartbeats",
        sa.Column("worker_id", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_job_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_category", sa.String(length=80), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["current_job_id"], ["localization_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("worker_id"),
    )


def downgrade() -> None:
    op.drop_table("localization_worker_heartbeats")
    op.drop_index("ix_localization_jobs_resource", table_name="localization_jobs")
    op.drop_index("ix_localization_jobs_due", table_name="localization_jobs")
    op.drop_index("ix_localization_jobs_next_attempt_at", table_name="localization_jobs")
    op.drop_index("ix_localization_jobs_status", table_name="localization_jobs")
    op.drop_index("ix_localization_jobs_entity_uuid", table_name="localization_jobs")
    op.drop_table("localization_jobs")
    op.drop_index("ix_knowledge_localizations_source_hash", table_name="knowledge_localizations")
    op.drop_index("ix_knowledge_localizations_review", table_name="knowledge_localizations")
    op.drop_index("ix_knowledge_localizations_resource_language", table_name="knowledge_localizations")
    op.drop_index("ix_knowledge_localizations_entity_language", table_name="knowledge_localizations")
    op.drop_table("knowledge_localizations")
