"""knowledge platform foundation

Revision ID: knowledge_2a1_20260723
Revises: postgres_foundation_20260722
Create Date: 2026-07-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "knowledge_2a1_20260723"
down_revision = "postgres_foundation_20260722"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "knowledge_providers",
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("provider_name", sa.String(length=120), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("rate_limit", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("health", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supports_entities", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("supports_media", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("supports_search", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("priority >= 0", name="ck_knowledge_provider_priority_nonnegative"),
        sa.PrimaryKeyConstraint("provider_id"),
        sa.UniqueConstraint("provider_name"),
    )
    op.create_index(
        "ix_knowledge_providers_enabled_priority",
        "knowledge_providers",
        ["enabled", "priority"],
    )

    op.create_table(
        "knowledge_entity_types",
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("entity_type"),
        sa.UniqueConstraint("display_name"),
    )

    op.create_table(
        "knowledge_entities",
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("language_neutral_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("source_priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="public"),
        sa.Column("search_weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("media_id", sa.Uuid(), nullable=True),
        sa.Column("thumbnail_id", sa.Uuid(), nullable=True),
        sa.Column("icon_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("search_weight >= 0", name="ck_knowledge_entity_search_weight_nonnegative"),
        sa.CheckConstraint("source_priority >= 0", name="ck_knowledge_entity_source_priority_nonnegative"),
        sa.CheckConstraint("visibility IN ('public', 'internal', 'private')", name="ck_knowledge_entity_visibility"),
        sa.ForeignKeyConstraint(
            ["entity_type"],
            ["knowledge_entity_types.entity_type"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("uuid"),
        sa.UniqueConstraint("entity_type", "language_neutral_id", name="uq_knowledge_entity_type_language_neutral_id"),
        sa.UniqueConstraint("entity_type", "slug", name="uq_knowledge_entity_type_slug"),
    )
    op.create_index("ix_knowledge_entities_type_status", "knowledge_entities", ["entity_type", "status"])
    op.create_index(
        "ix_knowledge_entities_visibility_weight",
        "knowledge_entities",
        ["visibility", "search_weight"],
    )

    op.create_table(
        "knowledge_entity_aliases",
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("entity_uuid", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("normalized_alias", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["entity_uuid"], ["knowledge_entities.uuid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uuid"),
        sa.UniqueConstraint("entity_type", "normalized_alias", name="uq_knowledge_alias_type_normalized"),
    )
    op.create_index("ix_knowledge_alias_entity", "knowledge_entity_aliases", ["entity_uuid"])

    op.create_table(
        "knowledge_documents",
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("provider_document_id", sa.String(length=512), nullable=False),
        sa.Column("entity_uuid", sa.Uuid(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=128), nullable=True),
        sa.Column("etag", sa.String(length=512), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(["entity_uuid"], ["knowledge_entities.uuid"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_id"], ["knowledge_providers.provider_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("uuid"),
    )
    op.create_index("ix_knowledge_documents_checksum", "knowledge_documents", ["checksum"])
    op.create_index(
        "ix_knowledge_documents_entity_retrieved",
        "knowledge_documents",
        ["entity_uuid", "retrieved_at"],
    )
    op.create_index(
        "ix_knowledge_documents_provider_document_retrieved",
        "knowledge_documents",
        ["provider_id", "provider_document_id", "retrieved_at"],
    )
    op.create_index(
        "ix_knowledge_documents_raw_json_gin",
        "knowledge_documents",
        ["raw_json"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_knowledge_documents_metadata_gin",
        "knowledge_documents",
        ["metadata"],
        postgresql_using="gin",
    )

    op.create_table(
        "knowledge_search_metadata",
        sa.Column("entity_uuid", sa.Uuid(), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("search_tokens", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("provider_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("entity_popularity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("future_embedding_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["entity_uuid"], ["knowledge_entities.uuid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("entity_uuid"),
    )
    op.create_index("ix_knowledge_search_normalized_name", "knowledge_search_metadata", ["normalized_name"])
    op.create_index("ix_knowledge_search_provider_score", "knowledge_search_metadata", ["provider_score"])
    op.create_index("ix_knowledge_search_popularity", "knowledge_search_metadata", ["entity_popularity"])
    op.create_index(
        "ix_knowledge_search_tokens_gin",
        "knowledge_search_metadata",
        ["search_tokens"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_knowledge_search_aliases_gin",
        "knowledge_search_metadata",
        ["aliases"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_knowledge_search_name_trgm",
        "knowledge_search_metadata",
        ["normalized_name"],
        postgresql_using="gin",
        postgresql_ops={"normalized_name": "gin_trgm_ops"},
    )

    op.create_table(
        "knowledge_domain_events",
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("entity_uuid", sa.Uuid(), nullable=True),
        sa.Column("provider_id", sa.String(length=64), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["entity_uuid"], ["knowledge_entities.uuid"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_id"], ["knowledge_providers.provider_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("uuid"),
    )
    op.create_index("ix_knowledge_events_type_occurred", "knowledge_domain_events", ["event_type", "occurred_at"])
    op.create_index("ix_knowledge_events_unprocessed", "knowledge_domain_events", ["processed_at", "occurred_at"])

    provider_table = sa.table(
        "knowledge_providers",
        sa.column("provider_id", sa.String()),
        sa.column("provider_name", sa.String()),
        sa.column("priority", sa.Integer()),
        sa.column("enabled", sa.Boolean()),
        sa.column("version", sa.String()),
        sa.column("rate_limit", postgresql.JSONB()),
        sa.column("health", sa.String()),
        sa.column("supports_entities", postgresql.JSONB()),
        sa.column("supports_media", sa.Boolean()),
        sa.column("supports_search", sa.Boolean()),
    )
    op.bulk_insert(
        provider_table,
        [
            {
                "provider_id": "tibiadata",
                "provider_name": "TibiaData",
                "priority": 10,
                "enabled": True,
                "version": "v4",
                "rate_limit": {"requests": 30, "window_seconds": 60},
                "health": "unknown",
                "supports_entities": ["creature", "guild", "character", "world", "spell", "boss"],
                "supports_media": False,
                "supports_search": True,
            },
            {
                "provider_id": "tibiamaps",
                "provider_name": "TibiaMaps",
                "priority": 20,
                "enabled": True,
                "version": "1",
                "rate_limit": {"requests": 30, "window_seconds": 60},
                "health": "unknown",
                "supports_entities": ["area", "town", "hunt_zone", "access"],
                "supports_media": True,
                "supports_search": False,
            },
        ],
    )

    entity_type_table = sa.table(
        "knowledge_entity_types",
        sa.column("entity_type", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("enabled", sa.Boolean()),
        sa.column("metadata", postgresql.JSONB()),
    )
    op.bulk_insert(
        entity_type_table,
        [
            {"entity_type": entity_type, "display_name": display_name, "enabled": True, "metadata": {}}
            for entity_type, display_name in (
                ("creature", "Creature"),
                ("item", "Item"),
                ("quest", "Quest"),
                ("npc", "NPC"),
                ("spell", "Spell"),
                ("achievement", "Achievement"),
                ("imbuement", "Imbuement"),
                ("bestiary", "Bestiary"),
                ("boss", "Boss"),
                ("guild", "Guild"),
                ("character", "Character"),
                ("world", "World"),
                ("hunt_zone", "Hunt Zone"),
                ("access", "Access"),
                ("area", "Area"),
                ("town", "Town"),
            )
        ],
    )


def downgrade() -> None:
    op.drop_table("knowledge_domain_events")
    op.drop_table("knowledge_search_metadata")
    op.drop_table("knowledge_documents")
    op.drop_table("knowledge_entity_aliases")
    op.drop_table("knowledge_entities")
    op.drop_table("knowledge_entity_types")
    op.drop_table("knowledge_providers")
