"""quest knowledge adapter, missions, access, and relationships

Revision ID: knowledge_quest_20260724
Revises: knowledge_item_20260724
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "knowledge_quest_20260724"
down_revision = "knowledge_item_20260724"
branch_labels = None
depends_on = None


JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.drop_index("ix_tibiawiki_quests_name", table_name="tibiawiki_quests")
    op.create_index("ix_tibiawiki_quests_name", "tibiawiki_quests", ["name"], unique=False)
    for column in (
        sa.Column("normalized_name", sa.String(length=255), nullable=True),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column("source_name", sa.String(length=50), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("knowledge_entity_id", sa.Uuid(), nullable=True),
        sa.Column("data_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("protected_fields", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("quest_type", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("difficulty", sa.String(length=100), nullable=True),
        sa.Column("premium_required", sa.Boolean(), nullable=True),
        sa.Column("repeatable", sa.Boolean(), nullable=True),
        sa.Column("solo_possible", sa.Boolean(), nullable=True),
    ):
        op.add_column("tibiawiki_quests", column)
    for name, default in (
        ("starting_npcs", "'[]'::jsonb"),
        ("related_npcs", "'[]'::jsonb"),
        ("required_items", "'[]'::jsonb"),
        ("rewarded_items", "'[]'::jsonb"),
        ("required_quests", "'[]'::jsonb"),
        ("unlocked_quests", "'[]'::jsonb"),
        ("required_creatures", "'[]'::jsonb"),
        ("bosses", "'[]'::jsonb"),
        ("locations", "'[]'::jsonb"),
        ("access_unlocks", "'[]'::jsonb"),
        ("parser_metadata", "'{}'::jsonb"),
    ):
        op.add_column(
            "tibiawiki_quests",
            sa.Column(name, JSONB, nullable=False, server_default=sa.text(default)),
        )
    op.create_foreign_key(
        "fk_tibiawiki_quests_knowledge_entity", "tibiawiki_quests", "knowledge_entities",
        ["knowledge_entity_id"], ["uuid"], ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_tibiawiki_quests_source_external", "tibiawiki_quests", ["source_name", "external_id"]
    )
    op.create_index(
        "uq_tibiawiki_quests_knowledge_entity_id", "tibiawiki_quests", ["knowledge_entity_id"], unique=True
    )
    for name, columns in (
        ("ix_tibiawiki_quests_normalized_name", ["normalized_name"]),
        ("ix_tibiawiki_quests_external_id", ["external_id"]),
        ("ix_tibiawiki_quests_source_name", ["source_name"]),
        ("ix_tibiawiki_quests_quest_type", ["quest_type"]),
        ("ix_tibiawiki_quests_category", ["category"]),
        ("ix_tibiawiki_quests_premium_required", ["premium_required"]),
        ("ix_tibiawiki_quests_repeatable", ["repeatable"]),
    ):
        op.create_index(name, "tibiawiki_quests", columns)
    op.execute(
        "UPDATE tibiawiki_quests SET normalized_name = "
        "lower(trim(regexp_replace(unaccent(name), '[^[:alnum:]]+', ' ', 'g'))) "
        "WHERE normalized_name IS NULL"
    )

    op.create_table(
        "quest_missions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quest_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("identity_key", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("normalized_title", sa.String(length=255), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("objectives", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("required_items", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("rewarded_items", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("related_npcs", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("related_creatures", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("locations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("supplied_fields", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("protected_fields", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["quest_id"], ["tibiawiki_quests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["knowledge_providers.provider_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quest_id", "provider_id", "identity_key", name="uq_quest_mission_identity"),
        sa.UniqueConstraint("quest_id", "sequence", name="uq_quest_mission_sequence"),
    )
    op.create_index("ix_quest_missions_quest_sequence", "quest_missions", ["quest_id", "sequence"])

    op.create_table(
        "knowledge_accesses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_entity_id", sa.Uuid(), nullable=False),
        sa.Column("access_code", sa.String(length=255), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unlocked_by_quest_entity_uuid", sa.Uuid(), nullable=True),
        sa.Column("required_quests", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("required_items", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("destination_name", sa.String(length=255), nullable=True),
        sa.Column("provider_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("protected_fields", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["knowledge_entity_id"], ["knowledge_entities.uuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unlocked_by_quest_entity_uuid"], ["knowledge_entities.uuid"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("access_code"),
    )
    op.create_index("uq_knowledge_access_entity", "knowledge_accesses", ["knowledge_entity_id"], unique=True)
    op.create_index("ix_knowledge_access_normalized_name", "knowledge_accesses", ["normalized_name"])

    op.create_table(
        "knowledge_quest_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("quest_entity_uuid", sa.Uuid(), nullable=False),
        sa.Column("mission_id", sa.Uuid(), nullable=True),
        sa.Column("scope_key", sa.String(length=512), nullable=False, server_default="quest"),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("target_entity_type", sa.String(length=64), nullable=False),
        sa.Column("target_entity_uuid", sa.Uuid(), nullable=True),
        sa.Column("target_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_target_name", sa.String(length=255), nullable=False),
        sa.Column("resolution_status", sa.String(length=32), nullable=False, server_default="unresolved"),
        sa.Column("confidence", sa.String(length=32), nullable=False, server_default="exact"),
        sa.Column("source_document_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_contexts", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("protected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "resolution_status IN ('resolved','unresolved','ambiguous')",
            name="ck_knowledge_quest_relation_resolution",
        ),
        sa.ForeignKeyConstraint(["mission_id"], ["quest_missions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["knowledge_providers.provider_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["quest_entity_uuid"], ["knowledge_entities.uuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_entity_uuid"], ["knowledge_entities.uuid"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_id", "quest_entity_uuid", "scope_key", "relation_type",
            "target_entity_type", "normalized_target_name",
            name="uq_knowledge_quest_relation_fact",
        ),
    )
    op.create_index("ix_knowledge_quest_relations_quest", "knowledge_quest_relations", ["quest_entity_uuid"])
    op.create_index("ix_knowledge_quest_relations_target", "knowledge_quest_relations", ["target_entity_uuid"])
    op.create_index("ix_knowledge_quest_relations_mission", "knowledge_quest_relations", ["mission_id"])
    op.execute(
        "UPDATE knowledge_providers SET supports_entities='[\"creature\", \"item\", \"quest\"]'::jsonb, "
        "enabled=false, health='disabled' WHERE provider_id='tibiawiki'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE knowledge_providers SET supports_entities='[\"creature\", \"item\"]'::jsonb "
        "WHERE provider_id='tibiawiki'"
    )
    op.drop_table("knowledge_quest_relations")
    op.drop_table("knowledge_accesses")
    op.drop_table("quest_missions")
    for name in (
        "ix_tibiawiki_quests_repeatable", "ix_tibiawiki_quests_premium_required",
        "ix_tibiawiki_quests_category", "ix_tibiawiki_quests_quest_type",
        "ix_tibiawiki_quests_source_name", "ix_tibiawiki_quests_external_id",
        "ix_tibiawiki_quests_normalized_name", "uq_tibiawiki_quests_knowledge_entity_id",
    ):
        op.drop_index(name, table_name="tibiawiki_quests")
    op.drop_constraint("uq_tibiawiki_quests_source_external", "tibiawiki_quests", type_="unique")
    op.drop_constraint("fk_tibiawiki_quests_knowledge_entity", "tibiawiki_quests", type_="foreignkey")
    for name in (
        "parser_metadata", "access_unlocks", "locations", "bosses", "required_creatures",
        "unlocked_quests", "required_quests", "rewarded_items", "required_items", "related_npcs",
        "starting_npcs", "solo_possible", "repeatable", "premium_required", "difficulty", "category",
        "quest_type", "protected_fields", "data_version", "knowledge_entity_id", "image_url", "summary",
        "source_name", "external_id", "normalized_name",
    ):
        op.drop_column("tibiawiki_quests", name)
    op.drop_index("ix_tibiawiki_quests_name", table_name="tibiawiki_quests")
    op.create_index("ix_tibiawiki_quests_name", "tibiawiki_quests", ["name"], unique=True)
