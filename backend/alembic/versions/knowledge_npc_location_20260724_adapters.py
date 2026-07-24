"""NPC and location knowledge adapter bridges

Revision ID: knowledge_npc_location_20260724
Revises: knowledge_graph_20260724
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "knowledge_npc_location_20260724"
down_revision = "knowledge_graph_20260724"
branch_labels = None
depends_on = None


JSONB = postgresql.JSONB(astext_type=sa.Text())


def _common_columns():
    return (
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(180), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("source_name", sa.String(50), nullable=False),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("image_url", sa.String(1024), nullable=True),
        sa.Column("knowledge_entity_id", sa.Uuid(), nullable=False),
    )


def _metadata_columns():
    return (
        sa.Column("provider_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("supplied_fields", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("protected_fields", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("data_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def upgrade() -> None:
    op.create_table(
        "tibiawiki_npcs",
        *_common_columns(),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("occupation", sa.String(255), nullable=True),
        sa.Column("sex", sa.String(32), nullable=True),
        sa.Column("location_name", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("buys", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sells", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("destinations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("related_quests", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        *_metadata_columns(),
        sa.ForeignKeyConstraint(["knowledge_entity_id"], ["knowledge_entities.uuid"], ondelete="CASCADE"),
        sa.UniqueConstraint("source_name", "external_id", name="uq_tibiawiki_npcs_source_external"),
    )
    op.create_table(
        "tibiawiki_locations",
        *_common_columns(),
        sa.Column("location_kind", sa.String(100), nullable=True),
        sa.Column("region", sa.String(255), nullable=True),
        sa.Column("parent_location", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("premium_required", sa.Boolean(), nullable=True),
        sa.Column("minimum_level", sa.Integer(), nullable=True),
        sa.Column("maximum_level", sa.Integer(), nullable=True),
        sa.Column("npcs", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("creatures", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("quests", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sublocations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("access_notes", sa.Text(), nullable=True),
        *_metadata_columns(),
        sa.ForeignKeyConstraint(["knowledge_entity_id"], ["knowledge_entities.uuid"], ondelete="CASCADE"),
        sa.UniqueConstraint("source_name", "external_id", name="uq_tibiawiki_locations_source_external"),
    )
    for table, indexes in (
        ("tibiawiki_npcs", ("name", "normalized_name", "slug", "external_id", "source_name", "location_name")),
        ("tibiawiki_locations", ("name", "normalized_name", "slug", "external_id", "source_name", "location_kind", "region")),
    ):
        for column in indexes:
            op.create_index(f"ix_{table}_{column}", table, [column])
        op.create_index(f"uq_{table}_knowledge_entity_id", table, ["knowledge_entity_id"], unique=True)
    op.execute(
        "UPDATE knowledge_providers SET supports_entities='[\"creature\", \"item\", \"quest\", \"npc\", \"location\"]'::jsonb "
        "WHERE provider_id='tibiawiki'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE knowledge_providers SET supports_entities='[\"creature\", \"item\", \"quest\"]'::jsonb "
        "WHERE provider_id='tibiawiki'"
    )
    op.drop_table("tibiawiki_locations")
    op.drop_table("tibiawiki_npcs")
