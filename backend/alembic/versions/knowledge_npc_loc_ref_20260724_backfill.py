"""resolve exact historical NPC and location graph references

Revision ID: knowledge_npc_loc_ref_20260724
Revises: knowledge_npc_location_20260724
Create Date: 2026-07-24
"""

from alembic import op


revision = "knowledge_npc_loc_ref_20260724"
down_revision = "knowledge_npc_location_20260724"
branch_labels = None
depends_on = None


_EXACT_MATCHES = """
    WITH canonical_names AS (
        SELECT uuid AS entity_uuid, entity_type,
            lower(trim(regexp_replace(unaccent(canonical_name), '[^[:alnum:]]+', ' ', 'g'))) AS normalized_name
        FROM knowledge_entities
        WHERE entity_type IN ('npc', 'location')
        UNION
        SELECT entity_uuid, entity_type, normalized_alias
        FROM knowledge_entity_aliases
        WHERE entity_type IN ('npc', 'location')
    ),
    exact_matches AS (
        SELECT relationship.id AS relationship_id,
            min(canonical.entity_uuid::text)::uuid AS entity_uuid
        FROM knowledge_relationships AS relationship
        JOIN canonical_names AS canonical
          ON canonical.entity_type = relationship.target_entity_type_id
         AND canonical.normalized_name = relationship.normalized_unresolved_name
        WHERE relationship.is_current
          AND NOT relationship.manual_override
          AND relationship.resolution_state IN ('unresolved', 'ambiguous')
          AND relationship.target_entity_type_id IN ('npc', 'location')
        GROUP BY relationship.id
        HAVING count(DISTINCT canonical.entity_uuid) = 1
    )
"""


def upgrade() -> None:
    op.execute(_EXACT_MATCHES + """
        INSERT INTO knowledge_relationships (
            id, source_entity_id, source_scope, relationship_type_code,
            target_entity_id, target_entity_type_id, unresolved_name,
            normalized_unresolved_name, target_identity, resolution_state,
            confidence, source_provider_id, source_document_id, source_job_id,
            provenance_key, source_context, manual_override, verified_by_id,
            verified_at, valid_from, valid_until, is_current,
            superseded_by_id, rejection_reason
        )
        SELECT gen_random_uuid(), original.source_entity_id, original.source_scope,
            original.relationship_type_code, match.entity_uuid,
            original.target_entity_type_id, NULL, NULL,
            'entity:' || match.entity_uuid::text, 'resolved', 'high',
            original.source_provider_id, original.source_document_id,
            original.source_job_id, original.provenance_key,
            coalesce(original.source_context, '{}'::jsonb) || jsonb_build_object(
                'resolution_policy', 'exact_name_or_alias_only',
                'resolved_from', original.id::text,
                'previous_resolution_state', original.resolution_state,
                'resolution_migration', 'knowledge_npc_loc_ref_20260724'
            ),
            false, NULL, NULL, now(), NULL, true, NULL, NULL
        FROM exact_matches AS match
        JOIN knowledge_relationships AS original ON original.id = match.relationship_id
        ON CONFLICT (
            source_entity_id, source_scope, relationship_type_code,
            target_identity, provenance_key
        ) WHERE is_current DO NOTHING
    """)
    op.execute(_EXACT_MATCHES + """
        UPDATE knowledge_relationships AS original
        SET is_current = false,
            resolution_state = 'superseded',
            valid_until = now(),
            superseded_by_id = replacement.id,
            updated_at = now()
        FROM exact_matches AS match
        JOIN knowledge_relationships AS replacement
          ON replacement.target_entity_id = match.entity_uuid
         AND replacement.is_current
        WHERE original.id = match.relationship_id
          AND replacement.source_entity_id = original.source_entity_id
          AND replacement.source_scope = original.source_scope
          AND replacement.relationship_type_code = original.relationship_type_code
          AND replacement.provenance_key = original.provenance_key
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE knowledge_relationships
        SET is_current = false,
            resolution_state = 'superseded',
            valid_until = now(),
            updated_at = now()
        WHERE source_context->>'resolution_migration' = 'knowledge_npc_loc_ref_20260724'
    """)
    op.execute("""
        UPDATE knowledge_relationships AS original
        SET is_current = true,
            resolution_state = coalesce(
                replacement.source_context->>'previous_resolution_state',
                'unresolved'
            ),
            valid_until = NULL,
            superseded_by_id = NULL,
            updated_at = now()
        FROM knowledge_relationships AS replacement
        WHERE replacement.source_context->>'resolution_migration' = 'knowledge_npc_loc_ref_20260724'
          AND original.superseded_by_id = replacement.id
          AND NOT original.manual_override
    """)
    op.execute("""
        DELETE FROM knowledge_relationships
        WHERE source_context->>'resolution_migration' = 'knowledge_npc_loc_ref_20260724'
    """)
