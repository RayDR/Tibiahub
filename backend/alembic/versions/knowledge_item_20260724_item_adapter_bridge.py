"""item knowledge adapter bridge and creature-drop relationships

Revision ID: knowledge_item_20260724
Revises: knowledge_creature_20260723
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "knowledge_item_20260724"
down_revision = "knowledge_creature_20260723"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_tibiawiki_items_name", table_name="tibiawiki_items")
    op.create_index("ix_tibiawiki_items_name", "tibiawiki_items", ["name"], unique=False)
    op.add_column("tibiawiki_items", sa.Column("normalized_name", sa.String(length=255), nullable=True))
    op.add_column("tibiawiki_items", sa.Column("slug", sa.String(length=255), nullable=True))
    op.add_column("tibiawiki_items", sa.Column("external_id", sa.String(length=100), nullable=True))
    op.add_column("tibiawiki_items", sa.Column("source_name", sa.String(length=50), nullable=True))
    op.add_column("tibiawiki_items", sa.Column("source_url", sa.String(length=1024), nullable=True))
    op.add_column("tibiawiki_items", sa.Column("image_url", sa.String(length=1024), nullable=True))
    op.add_column("tibiawiki_items", sa.Column("knowledge_entity_id", sa.Uuid(), nullable=True))
    op.add_column("tibiawiki_items", sa.Column("data_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(
        "tibiawiki_items",
        sa.Column(
            "protected_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column("tibiawiki_items", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("tibiawiki_items", sa.Column("item_class", sa.String(length=100), nullable=True))
    op.add_column("tibiawiki_items", sa.Column("category", sa.String(length=100), nullable=True))
    op.add_column("tibiawiki_items", sa.Column("range", sa.Integer(), nullable=True))
    op.add_column("tibiawiki_items", sa.Column("imbuement_slots", sa.Integer(), nullable=True))
    for name, default in (
        ("slots", "'[]'::jsonb"),
        ("attributes", "'{}'::jsonb"),
        ("resistances", "'{}'::jsonb"),
        ("bonuses", "'{}'::jsonb"),
        ("vocation_requirements", "'[]'::jsonb"),
        ("buy_from", "'[]'::jsonb"),
        ("sell_to", "'[]'::jsonb"),
        ("rewards_from", "'[]'::jsonb"),
        ("required_for", "'[]'::jsonb"),
    ):
        op.add_column(
            "tibiawiki_items",
            sa.Column(
                name,
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text(default),
            ),
        )
    op.add_column("tibiawiki_items", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_tibiawiki_items_knowledge_entity",
        "tibiawiki_items",
        "knowledge_entities",
        ["knowledge_entity_id"],
        ["uuid"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_tibiawiki_items_source_external",
        "tibiawiki_items",
        ["source_name", "external_id"],
    )
    op.create_index(
        "uq_tibiawiki_items_knowledge_entity_id",
        "tibiawiki_items",
        ["knowledge_entity_id"],
        unique=True,
    )
    for name, columns in (
        ("ix_tibiawiki_items_normalized_name", ["normalized_name"]),
        ("ix_tibiawiki_items_slug", ["slug"]),
        ("ix_tibiawiki_items_external_id", ["external_id"]),
        ("ix_tibiawiki_items_source_name", ["source_name"]),
        ("ix_tibiawiki_items_item_class", ["item_class"]),
        ("ix_tibiawiki_items_category", ["category"]),
    ):
        op.create_index(name, "tibiawiki_items", columns)
    op.execute(
        "UPDATE tibiawiki_items SET normalized_name = "
        "lower(trim(regexp_replace(unaccent(name), '[^[:alnum:]]+', ' ', 'g'))) "
        "WHERE normalized_name IS NULL"
    )

    op.create_table(
        "knowledge_creature_item_drops",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("creature_entity_uuid", sa.Uuid(), nullable=True),
        sa.Column("item_entity_uuid", sa.Uuid(), nullable=True),
        sa.Column("creature_name", sa.String(length=255), nullable=False),
        sa.Column("item_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_creature_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_item_name", sa.String(length=255), nullable=False),
        sa.Column("resolution_status", sa.String(length=32), nullable=False, server_default="unresolved"),
        sa.Column("confidence", sa.String(length=32), nullable=False, server_default="exact"),
        sa.Column(
            "source_document_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "source_directions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "resolution_status IN ('resolved','unresolved','ambiguous')",
            name="ck_knowledge_creature_item_drop_resolution",
        ),
        sa.ForeignKeyConstraint(["creature_entity_uuid"], ["knowledge_entities.uuid"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["item_entity_uuid"], ["knowledge_entities.uuid"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_id"], ["knowledge_providers.provider_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_id",
            "normalized_creature_name",
            "normalized_item_name",
            name="uq_knowledge_creature_item_drop_fact",
        ),
    )
    op.create_index(
        "ix_knowledge_creature_item_drops_creature",
        "knowledge_creature_item_drops",
        ["creature_entity_uuid"],
    )
    op.create_index(
        "ix_knowledge_creature_item_drops_item",
        "knowledge_creature_item_drops",
        ["item_entity_uuid"],
    )
    op.execute(
        "UPDATE knowledge_providers SET supports_entities='[\"creature\", \"item\"]'::jsonb, "
        "enabled=false, health='disabled' WHERE provider_id='tibiawiki'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE knowledge_providers SET supports_entities='[\"creature\"]'::jsonb "
        "WHERE provider_id='tibiawiki'"
    )
    op.drop_table("knowledge_creature_item_drops")
    for name in (
        "ix_tibiawiki_items_category",
        "ix_tibiawiki_items_item_class",
        "ix_tibiawiki_items_source_name",
        "ix_tibiawiki_items_external_id",
        "ix_tibiawiki_items_slug",
        "ix_tibiawiki_items_normalized_name",
        "uq_tibiawiki_items_knowledge_entity_id",
    ):
        op.drop_index(name, table_name="tibiawiki_items")
    op.drop_constraint("uq_tibiawiki_items_source_external", "tibiawiki_items", type_="unique")
    op.drop_constraint("fk_tibiawiki_items_knowledge_entity", "tibiawiki_items", type_="foreignkey")
    for name in (
        "last_synced_at",
        "required_for",
        "rewards_from",
        "sell_to",
        "buy_from",
        "vocation_requirements",
        "bonuses",
        "resistances",
        "attributes",
        "slots",
        "imbuement_slots",
        "range",
        "category",
        "item_class",
        "notes",
        "protected_fields",
        "data_version",
        "knowledge_entity_id",
        "image_url",
        "source_url",
        "source_name",
        "external_id",
        "slug",
        "normalized_name",
    ):
        op.drop_column("tibiawiki_items", name)
    op.drop_index("ix_tibiawiki_items_name", table_name="tibiawiki_items")
    op.create_index("ix_tibiawiki_items_name", "tibiawiki_items", ["name"], unique=True)
