"""Add durable localized content and review metadata.

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
    op.create_index(
        "ix_knowledge_localizations_entity_language",
        "knowledge_localizations",
        ["entity_uuid", "language"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_localizations_resource_language",
        "knowledge_localizations",
        ["resource_type", "resource_key", "language"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_localizations_review",
        "knowledge_localizations",
        ["status", "language", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_localizations_source_hash",
        "knowledge_localizations",
        ["source_text_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_localizations_source_hash", table_name="knowledge_localizations")
    op.drop_index("ix_knowledge_localizations_review", table_name="knowledge_localizations")
    op.drop_index("ix_knowledge_localizations_resource_language", table_name="knowledge_localizations")
    op.drop_index("ix_knowledge_localizations_entity_language", table_name="knowledge_localizations")
    op.drop_table("knowledge_localizations")
