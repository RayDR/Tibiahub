"""creature knowledge adapter bridge

Revision ID: knowledge_creature_20260723
Revises: knowledge_workers_20260723
Create Date: 2026-07-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "knowledge_creature_20260723"
down_revision = "knowledge_workers_20260723"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_external_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("entity_type_id", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("entity_uuid", sa.Uuid(), nullable=False),
        sa.Column(
            "provider_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["entity_type_id"], ["knowledge_entity_types.entity_type"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_uuid"], ["knowledge_entities.uuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["knowledge_providers.provider_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_id",
            "entity_type_id",
            "external_id",
            name="uq_knowledge_external_mapping_identifier",
        ),
        sa.UniqueConstraint(
            "provider_id",
            "entity_type_id",
            "entity_uuid",
            name="uq_knowledge_external_mapping_entity",
        ),
    )
    op.create_index(
        "ix_knowledge_external_mappings_entity",
        "knowledge_external_mappings",
        ["entity_uuid"],
    )

    op.add_column("creatures", sa.Column("knowledge_entity_id", sa.Uuid(), nullable=True))
    op.add_column("creatures", sa.Column("data_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(
        "creatures",
        sa.Column(
            "protected_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_foreign_key(
        "fk_creatures_knowledge_entity",
        "creatures",
        "knowledge_entities",
        ["knowledge_entity_id"],
        ["uuid"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_creatures_knowledge_entity_id",
        "creatures",
        ["knowledge_entity_id"],
        unique=True,
    )

    op.execute(
        "INSERT INTO knowledge_providers "
        "(provider_id, provider_name, priority, enabled, version, rate_limit, health, "
        "supports_entities, supports_media, supports_search, consecutive_failures) "
        "VALUES ('tibiawiki', 'TibiaWiki', 20, false, 'mediawiki-v1', "
        "'{\"requests\": 12, \"window_seconds\": 60}'::jsonb, 'disabled', "
        "'[\"creature\"]'::jsonb, true, true, 0) "
        "ON CONFLICT (provider_id) DO UPDATE SET "
        "provider_name=EXCLUDED.provider_name, priority=EXCLUDED.priority, version=EXCLUDED.version, "
        "rate_limit=EXCLUDED.rate_limit, supports_entities=EXCLUDED.supports_entities, "
        "supports_media=EXCLUDED.supports_media, supports_search=EXCLUDED.supports_search, "
        "enabled=false, health='disabled'"
    )


def downgrade() -> None:
    op.drop_index("uq_creatures_knowledge_entity_id", table_name="creatures")
    op.drop_constraint("fk_creatures_knowledge_entity", "creatures", type_="foreignkey")
    op.drop_column("creatures", "protected_fields")
    op.drop_column("creatures", "data_version")
    op.drop_column("creatures", "knowledge_entity_id")
    op.drop_table("knowledge_external_mappings")
