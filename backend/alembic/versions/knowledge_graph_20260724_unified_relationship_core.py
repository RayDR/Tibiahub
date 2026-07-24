"""unified provenance-aware knowledge graph core

Revision ID: knowledge_graph_20260724
Revises: knowledge_quest_20260724
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "knowledge_graph_20260724"
down_revision = "knowledge_quest_20260724"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


RELATIONSHIP_TYPES = (
    ("drops", "dropped_by", ["creature"], ["item"]),
    ("dropped_by", "drops", ["item"], ["creature"]),
    ("requires_item", "required_by_quest", ["quest"], ["item"]),
    ("required_by_quest", "requires_item", ["item"], ["quest"]),
    ("rewards_item", "rewarded_by_quest", ["quest"], ["item"]),
    ("rewarded_by_quest", "rewards_item", ["item"], ["quest"]),
    ("requires_quest", "prerequisite_for", ["quest"], ["quest"]),
    ("prerequisite_for", "requires_quest", ["quest"], ["quest"]),
    ("unlocks_access", "unlocked_by_quest", ["quest"], ["access"]),
    ("unlocked_by_quest", "unlocks_access", ["access"], ["quest"]),
    ("involves_creature", "involved_in_quest", ["quest"], ["creature"]),
    ("involved_in_quest", "involves_creature", ["creature"], ["quest"]),
    ("involves_boss", "boss_in_quest", ["quest"], ["creature", "boss"]),
    ("boss_in_quest", "involves_boss", ["creature", "boss"], ["quest"]),
    ("starts_at_npc", "starts_quest", ["quest"], ["npc"]),
    ("starts_quest", "starts_at_npc", ["npc"], ["quest"]),
    ("references_npc", "referenced_by_quest", ["quest"], ["npc"]),
    ("referenced_by_quest", "references_npc", ["npc"], ["quest"]),
    ("occurs_at_location", "hosts_quest", ["quest"], ["area", "town", "location"]),
    ("hosts_quest", "occurs_at_location", ["area", "town", "location"], ["quest"]),
    ("mission_requires_item", "required_by_mission", ["quest"], ["item"]),
    ("required_by_mission", "mission_requires_item", ["item"], ["quest"]),
    ("mission_rewards_item", "rewarded_by_mission", ["quest"], ["item"]),
    ("rewarded_by_mission", "mission_rewards_item", ["item"], ["quest"]),
    ("mission_involves_creature", "involved_in_mission", ["quest"], ["creature"]),
    ("involved_in_mission", "mission_involves_creature", ["creature"], ["quest"]),
    ("mission_references_npc", "referenced_by_mission", ["quest"], ["npc"]),
    ("referenced_by_mission", "mission_references_npc", ["npc"], ["quest"]),
    ("mission_occurs_at_location", "hosts_mission", ["quest"], ["area", "town", "location"]),
    ("hosts_mission", "mission_occurs_at_location", ["area", "town", "location"], ["quest"]),
)


def upgrade() -> None:
    op.execute(
        "INSERT INTO knowledge_entity_types (entity_type, display_name, enabled, metadata) "
        "VALUES ('location','Location',true,'{}'::jsonb) ON CONFLICT (entity_type) DO NOTHING"
    )
    op.create_table(
        "knowledge_relationship_types",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("display_translation_key", sa.String(160), nullable=False, unique=True),
        sa.Column("inverse_code", sa.String(64), nullable=False),
        sa.Column("source_entity_types", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("target_entity_types", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("directional", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("symmetric", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("transitive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("user_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ai_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["inverse_code"], ["knowledge_relationship_types.code"], ondelete="RESTRICT"),
    )
    types = sa.table(
        "knowledge_relationship_types",
        sa.column("code", sa.String), sa.column("display_translation_key", sa.String),
        sa.column("inverse_code", sa.String), sa.column("source_entity_types", JSONB),
        sa.column("target_entity_types", JSONB),
    )
    op.bulk_insert(types, [
        {"code": code, "display_translation_key": f"knowledgeGraph.relationships.{code}",
         "inverse_code": code, "source_entity_types": sources, "target_entity_types": targets}
        for code, _inverse, sources, targets in RELATIONSHIP_TYPES
    ])
    for code, inverse, _sources, _targets in RELATIONSHIP_TYPES:
        op.execute(sa.text("UPDATE knowledge_relationship_types SET inverse_code=:inverse WHERE code=:code").bindparams(code=code, inverse=inverse))

    op.create_table(
        "knowledge_relationships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_entity_id", sa.Uuid(), nullable=False),
        sa.Column("source_scope", sa.String(512), nullable=False, server_default="entity"),
        sa.Column("relationship_type_code", sa.String(64), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=True),
        sa.Column("target_entity_type_id", sa.String(64), nullable=True),
        sa.Column("unresolved_name", sa.String(255), nullable=True),
        sa.Column("normalized_unresolved_name", sa.String(255), nullable=True),
        sa.Column("target_identity", sa.String(600), nullable=False),
        sa.Column("resolution_state", sa.String(32), nullable=False, server_default="unresolved"),
        sa.Column("confidence", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("source_provider_id", sa.String(64), nullable=True),
        sa.Column("source_document_id", sa.Uuid(), nullable=True),
        sa.Column("source_job_id", sa.Uuid(), nullable=True),
        sa.Column("provenance_key", sa.String(255), nullable=False),
        sa.Column("source_context", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("manual_override", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verified_by_id", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("superseded_by_id", sa.Uuid(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("resolution_state IN ('resolved','unresolved','ambiguous','rejected','superseded')", name="ck_knowledge_relationship_state"),
        sa.CheckConstraint("confidence IN ('verified','high','medium','low','unknown')", name="ck_knowledge_relationship_confidence"),
        sa.CheckConstraint("(resolution_state <> 'resolved') OR (target_entity_id IS NOT NULL)", name="ck_knowledge_relationship_resolved_target"),
        sa.CheckConstraint("(resolution_state NOT IN ('unresolved','ambiguous')) OR (unresolved_name IS NOT NULL AND normalized_unresolved_name IS NOT NULL)", name="ck_knowledge_relationship_unresolved_name"),
        sa.CheckConstraint("target_entity_id IS NULL OR source_entity_id <> target_entity_id", name="ck_knowledge_relationship_not_self"),
        sa.CheckConstraint("superseded_by_id IS NULL OR superseded_by_id <> id", name="ck_knowledge_relationship_not_self_superseded"),
        sa.ForeignKeyConstraint(["source_entity_id"], ["knowledge_entities.uuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["relationship_type_code"], ["knowledge_relationship_types.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_entity_id"], ["knowledge_entities.uuid"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_entity_type_id"], ["knowledge_entity_types.entity_type"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_provider_id"], ["knowledge_providers.provider_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_document_id"], ["knowledge_documents.uuid"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_job_id"], ["knowledge_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["superseded_by_id"], ["knowledge_relationships.id"], ondelete="SET NULL"),
    )
    for name, columns in (
        ("ix_knowledge_relationships_source_current", ["source_entity_id", "is_current"]),
        ("ix_knowledge_relationships_target_current", ["target_entity_id", "is_current"]),
        ("ix_knowledge_relationships_type_current", ["relationship_type_code", "is_current"]),
        ("ix_knowledge_relationships_resolution", ["resolution_state", "is_current"]),
        ("ix_knowledge_relationships_provider", ["source_provider_id", "is_current"]),
        ("ix_knowledge_relationships_document", ["source_document_id"]),
        ("ix_knowledge_relationships_job", ["source_job_id"]),
    ):
        op.create_index(name, "knowledge_relationships", columns)
    op.create_index(
        "uq_knowledge_relationship_current_provenance", "knowledge_relationships",
        ["source_entity_id", "source_scope", "relationship_type_code", "target_identity", "provenance_key"],
        unique=True, postgresql_where=sa.text("is_current"),
    )

    # Bridge Creature/Item facts once. The orientation with a known source is
    # retained when the opposite endpoint remains unresolved.
    op.execute("""
        INSERT INTO knowledge_relationships (
            id, source_entity_id, source_scope, relationship_type_code,
            target_entity_id, target_entity_type_id, unresolved_name,
            normalized_unresolved_name, target_identity, resolution_state,
            confidence, source_provider_id, source_document_id, provenance_key,
            source_context, manual_override, is_current
        )
        SELECT gen_random_uuid(),
            COALESCE(d.creature_entity_uuid, d.item_entity_uuid), 'entity',
            CASE WHEN d.creature_entity_uuid IS NOT NULL THEN 'drops' ELSE 'dropped_by' END,
            CASE WHEN d.resolution_status='resolved' THEN
                CASE WHEN d.creature_entity_uuid IS NOT NULL THEN d.item_entity_uuid ELSE d.creature_entity_uuid END
            END,
            CASE WHEN d.creature_entity_uuid IS NOT NULL THEN 'item' ELSE 'creature' END,
            CASE WHEN d.resolution_status='resolved' THEN NULL
                WHEN d.creature_entity_uuid IS NOT NULL THEN d.item_name ELSE d.creature_name END,
            CASE WHEN d.resolution_status='resolved' THEN NULL
                WHEN d.creature_entity_uuid IS NOT NULL THEN d.normalized_item_name ELSE d.normalized_creature_name END,
            CASE WHEN d.resolution_status='resolved' THEN 'entity:' ||
                (CASE WHEN d.creature_entity_uuid IS NOT NULL THEN d.item_entity_uuid ELSE d.creature_entity_uuid END)::text
                ELSE 'name:' || (CASE WHEN d.creature_entity_uuid IS NOT NULL THEN 'item:' || d.normalized_item_name ELSE 'creature:' || d.normalized_creature_name END) END,
            d.resolution_status, CASE WHEN d.confidence='exact' THEN 'high' ELSE 'unknown' END,
            d.provider_id,
            (SELECT kd.uuid FROM knowledge_documents kd WHERE kd.provider_id=d.provider_id
                AND kd.provider_document_id=(d.source_document_ids->>0) ORDER BY kd.retrieved_at DESC LIMIT 1),
            'provider:' || d.provider_id,
            jsonb_build_object('legacy_table','knowledge_creature_item_drops','legacy_id',d.id::text,
                'source_document_refs',d.source_document_ids,'source_directions',d.source_directions),
            false, true
        FROM knowledge_creature_item_drops d
        WHERE COALESCE(d.creature_entity_uuid, d.item_entity_uuid) IS NOT NULL
        ON CONFLICT DO NOTHING
    """)

    op.execute("""
        INSERT INTO knowledge_relationships (
            id, source_entity_id, source_scope, relationship_type_code,
            target_entity_id, target_entity_type_id, unresolved_name,
            normalized_unresolved_name, target_identity, resolution_state,
            confidence, source_provider_id, source_document_id, provenance_key,
            source_context, manual_override, is_current
        )
        SELECT gen_random_uuid(), q.quest_entity_uuid,
            CASE WHEN q.mission_id IS NULL THEN 'quest' ELSE 'mission:' || q.mission_id::text END,
            CASE
                WHEN q.mission_id IS NOT NULL AND q.relation_type='requires_item' THEN 'mission_requires_item'
                WHEN q.mission_id IS NOT NULL AND q.relation_type='rewards_item' THEN 'mission_rewards_item'
                WHEN q.mission_id IS NOT NULL AND q.relation_type='involves_creature' THEN 'mission_involves_creature'
                WHEN q.mission_id IS NOT NULL AND q.relation_type='involves_npc' THEN 'mission_references_npc'
                WHEN q.mission_id IS NOT NULL AND q.relation_type='occurs_at_location' THEN 'mission_occurs_at_location'
                WHEN q.relation_type='involves_npc' THEN 'references_npc'
                WHEN q.relation_type='unlocks_quest' THEN 'prerequisite_for'
                ELSE q.relation_type END,
            CASE WHEN q.resolution_status='resolved' THEN q.target_entity_uuid END,
            COALESCE((SELECT e.entity_type FROM knowledge_entities e WHERE e.uuid=q.target_entity_uuid), q.target_entity_type),
            CASE WHEN q.resolution_status='resolved' THEN NULL ELSE q.target_name END,
            CASE WHEN q.resolution_status='resolved' THEN NULL ELSE q.normalized_target_name END,
            CASE WHEN q.resolution_status='resolved' THEN 'entity:' || q.target_entity_uuid::text
                ELSE 'name:' || q.target_entity_type || ':' || q.normalized_target_name END,
            q.resolution_status, CASE WHEN q.protected THEN 'verified' WHEN q.confidence='exact' THEN 'high' ELSE 'unknown' END,
            q.provider_id,
            (SELECT kd.uuid FROM knowledge_documents kd WHERE kd.provider_id=q.provider_id
                AND kd.provider_document_id=(q.source_document_ids->>0) ORDER BY kd.retrieved_at DESC LIMIT 1),
            CASE WHEN q.protected THEN 'manual:legacy' ELSE 'provider:' || q.provider_id END,
            jsonb_build_object('legacy_table','knowledge_quest_relations','legacy_id',q.id::text,
                'source_contexts',q.source_contexts,'legacy_scope',q.scope_key,
                'source_document_refs',q.source_document_ids),
            q.protected, true
        FROM knowledge_quest_relations q
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("knowledge_relationships")
    op.drop_table("knowledge_relationship_types")
    op.execute("DELETE FROM knowledge_entity_types WHERE entity_type='location' AND NOT EXISTS (SELECT 1 FROM knowledge_entities WHERE entity_type='location')")
