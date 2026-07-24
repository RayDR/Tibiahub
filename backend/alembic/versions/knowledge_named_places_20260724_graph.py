"""canonical named places and NPC/location/access graph relationships

Revision ID: knowledge_named_places_20260724
Revises: knowledge_npc_loc_ref_20260724
Create Date: 2026-07-24
"""

from alembic import op


revision = "knowledge_named_places_20260724"
down_revision = "knowledge_npc_loc_ref_20260724"
branch_labels = None
depends_on = None


RELATIONSHIP_TYPES = (
    ("located_at", "hosts_npc", '["npc"]', '["location", "area", "town"]'),
    ("hosts_npc", "located_at", '["location", "area", "town"]', '["npc"]'),
    ("contained_in", "contains", '["location", "area"]', '["area", "town"]'),
    ("contains", "contained_in", '["area", "town"]', '["location", "area"]'),
    ("leads_to", "destination_of_access", '["access"]', '["location", "area", "town"]'),
    ("destination_of_access", "leads_to", '["location", "area", "town"]', '["access"]'),
)


def _register_relationship_types() -> None:
    for code, _inverse, sources, targets in RELATIONSHIP_TYPES:
        op.execute(f"""
            INSERT INTO knowledge_relationship_types (
                code, display_translation_key, inverse_code,
                source_entity_types, target_entity_types
            ) VALUES (
                '{code}', 'knowledgeGraph.relationships.{code}', '{code}',
                '{sources}'::jsonb, '{targets}'::jsonb
            )
            ON CONFLICT (code) DO UPDATE SET
                display_translation_key = EXCLUDED.display_translation_key,
                source_entity_types = EXCLUDED.source_entity_types,
                target_entity_types = EXCLUDED.target_entity_types,
                active = true,
                updated_at = now()
        """)
    for code, inverse, _sources, _targets in RELATIONSHIP_TYPES:
        op.execute(
            f"UPDATE knowledge_relationship_types SET inverse_code='{inverse}', updated_at=now() WHERE code='{code}'"
        )


def _reclassify_existing_places() -> None:
    # Reclassify only unambiguous provider bridges. If a target-type canonical
    # name or alias already exists, retain the location for administrator review.
    op.execute("""
        CREATE TEMPORARY TABLE knowledge_place_reclassify_tmp ON COMMIT DROP AS
        WITH classified AS (
            SELECT bridge.knowledge_entity_id AS entity_uuid,
                CASE
                    WHEN lower(trim(bridge.location_kind)) IN ('city','settlement','town','village') THEN 'town'
                    WHEN lower(trim(bridge.location_kind)) IN ('area','continent','island','region') THEN 'area'
                END AS desired_type
            FROM tibiawiki_locations AS bridge
            JOIN knowledge_entities AS entity ON entity.uuid = bridge.knowledge_entity_id
            WHERE entity.entity_type = 'location'
        )
        SELECT classified.entity_uuid, classified.desired_type
        FROM classified
        JOIN knowledge_entities AS source ON source.uuid = classified.entity_uuid
        WHERE classified.desired_type IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM knowledge_entities AS candidate
              WHERE candidate.uuid <> source.uuid
                AND candidate.entity_type = classified.desired_type
                AND lower(trim(regexp_replace(unaccent(candidate.canonical_name), '[^[:alnum:]]+', ' ', 'g')))
                    = lower(trim(regexp_replace(unaccent(source.canonical_name), '[^[:alnum:]]+', ' ', 'g')))
          )
          AND NOT EXISTS (
              SELECT 1
              FROM knowledge_entity_aliases AS source_alias
              JOIN knowledge_entity_aliases AS candidate_alias
                ON candidate_alias.normalized_alias = source_alias.normalized_alias
               AND candidate_alias.entity_type = classified.desired_type
              WHERE source_alias.entity_uuid = source.uuid
          )
    """)
    op.execute("""
        UPDATE knowledge_external_mappings AS mapping
        SET entity_type_id = classified.desired_type, updated_at = now()
        FROM knowledge_place_reclassify_tmp AS classified
        WHERE mapping.entity_uuid = classified.entity_uuid
          AND mapping.entity_type_id = 'location'
    """)
    op.execute("""
        UPDATE knowledge_entity_aliases AS alias
        SET entity_type = classified.desired_type
        FROM knowledge_place_reclassify_tmp AS classified
        WHERE alias.entity_uuid = classified.entity_uuid
    """)
    op.execute("""
        UPDATE knowledge_relationships AS relationship
        SET target_entity_type_id = classified.desired_type, updated_at = now()
        FROM knowledge_place_reclassify_tmp AS classified
        WHERE relationship.target_entity_id = classified.entity_uuid
    """)
    op.execute("""
        UPDATE knowledge_entities AS entity
        SET entity_type = classified.desired_type,
            language_neutral_id = CASE
                WHEN entity.language_neutral_id LIKE 'location:tibiawiki:%'
                    THEN classified.desired_type || substr(entity.language_neutral_id, length('location') + 1)
                ELSE entity.language_neutral_id
            END,
            updated_at = now()
        FROM knowledge_place_reclassify_tmp AS classified
        WHERE entity.uuid = classified.entity_uuid
    """)


_NAMED_EDGE_FACTS = """
    WITH source_facts AS (
        SELECT npc.knowledge_entity_id AS source_entity_id,
            'location'::text AS source_scope, 'located_at'::text AS relationship_type,
            npc.location_name AS target_name, 'location'::text AS unresolved_type,
            ARRAY['location','area','town']::text[] AS candidate_types,
            npc.source_name AS provider_id, 'npc.location_name'::text AS fact_context
        FROM tibiawiki_npcs AS npc
        WHERE nullif(trim(npc.location_name), '') IS NOT NULL
        UNION ALL
        SELECT place.knowledge_entity_id, 'parent', 'contained_in',
            coalesce(nullif(trim(place.parent_location), ''), nullif(trim(place.region), '')),
            'area', ARRAY['area']::text[], place.source_name, 'location.parent_location_or_region'
        FROM tibiawiki_locations AS place
        JOIN knowledge_entities AS entity ON entity.uuid = place.knowledge_entity_id
        WHERE entity.entity_type = 'location'
          AND coalesce(nullif(trim(place.parent_location), ''), nullif(trim(place.region), '')) IS NOT NULL
        UNION ALL
        SELECT place.knowledge_entity_id, 'parent', 'contained_in',
            coalesce(nullif(trim(place.parent_location), ''), nullif(trim(place.region), '')),
            'town', ARRAY['town']::text[], place.source_name, 'area.parent_location_or_region'
        FROM tibiawiki_locations AS place
        JOIN knowledge_entities AS entity ON entity.uuid = place.knowledge_entity_id
        WHERE entity.entity_type = 'area'
          AND coalesce(nullif(trim(place.parent_location), ''), nullif(trim(place.region), '')) IS NOT NULL
        UNION ALL
        SELECT access.knowledge_entity_id, 'destination', 'leads_to', access.destination_name,
            'location', ARRAY['location','area','town']::text[],
            coalesce(nullif(access.provider_metadata->>'provider', ''), 'tibiawiki'),
            'access.destination_name'
        FROM knowledge_accesses AS access
        WHERE nullif(trim(access.destination_name), '') IS NOT NULL
    ),
    normalized_facts AS (
        SELECT fact.*,
            lower(trim(regexp_replace(unaccent(fact.target_name), '[^[:alnum:]]+', ' ', 'g'))) AS normalized_name
        FROM source_facts AS fact
    ),
    canonical_names AS (
        SELECT uuid AS entity_uuid, entity_type,
            lower(trim(regexp_replace(unaccent(canonical_name), '[^[:alnum:]]+', ' ', 'g'))) AS normalized_name
        FROM knowledge_entities
        WHERE entity_type IN ('location','area','town')
        UNION
        SELECT entity_uuid, entity_type, normalized_alias
        FROM knowledge_entity_aliases
        WHERE entity_type IN ('location','area','town')
    ),
    matches AS (
        SELECT fact.source_entity_id, fact.source_scope, fact.relationship_type,
            fact.target_name, fact.normalized_name, fact.unresolved_type,
            fact.provider_id, fact.fact_context,
            count(DISTINCT candidate.entity_uuid) AS match_count,
            min(candidate.entity_uuid::text)::uuid AS target_entity_id
        FROM normalized_facts AS fact
        LEFT JOIN canonical_names AS candidate
          ON candidate.entity_type = ANY(fact.candidate_types)
         AND candidate.normalized_name = fact.normalized_name
         AND candidate.entity_uuid <> fact.source_entity_id
        GROUP BY fact.source_entity_id, fact.source_scope, fact.relationship_type,
            fact.target_name, fact.normalized_name, fact.unresolved_type,
            fact.provider_id, fact.fact_context
    )
"""


def _backfill_named_edges() -> None:
    op.execute(_NAMED_EDGE_FACTS + """
        INSERT INTO knowledge_relationships (
            id, source_entity_id, source_scope, relationship_type_code,
            target_entity_id, target_entity_type_id, unresolved_name,
            normalized_unresolved_name, target_identity, resolution_state,
            confidence, source_provider_id, provenance_key, source_context,
            manual_override, valid_from, is_current
        )
        SELECT gen_random_uuid(), match.source_entity_id, match.source_scope,
            match.relationship_type,
            CASE WHEN match.match_count = 1 THEN match.target_entity_id END,
            CASE WHEN match.match_count = 1 THEN target.entity_type ELSE match.unresolved_type END,
            CASE WHEN match.match_count = 1 THEN NULL ELSE match.target_name END,
            CASE WHEN match.match_count = 1 THEN NULL ELSE match.normalized_name END,
            CASE WHEN match.match_count = 1
                THEN 'entity:' || match.target_entity_id::text
                ELSE 'name:' || match.unresolved_type || ':' || match.normalized_name END,
            CASE WHEN match.match_count = 1 THEN 'resolved'
                 WHEN match.match_count > 1 THEN 'ambiguous' ELSE 'unresolved' END,
            'high', match.provider_id, 'provider:' || match.provider_id,
            jsonb_build_object(
                'context', match.fact_context,
                'resolution_policy', 'exact_name_or_alias_only',
                'resolution_migration', 'knowledge_named_places_20260724',
                'candidate_count', match.match_count
            ),
            false, now(), true
        FROM matches AS match
        LEFT JOIN knowledge_entities AS target ON target.uuid = match.target_entity_id
        ON CONFLICT (
            source_entity_id, source_scope, relationship_type_code,
            target_identity, provenance_key
        ) WHERE is_current DO NOTHING
    """)


_QUEST_PLACE_MATCHES = """
    WITH canonical_names AS (
        SELECT uuid AS entity_uuid, entity_type,
            lower(trim(regexp_replace(unaccent(canonical_name), '[^[:alnum:]]+', ' ', 'g'))) AS normalized_name
        FROM knowledge_entities
        WHERE entity_type IN ('location','area','town')
        UNION
        SELECT entity_uuid, entity_type, normalized_alias
        FROM knowledge_entity_aliases
        WHERE entity_type IN ('location','area','town')
    ),
    exact_matches AS (
        SELECT relationship.id AS relationship_id,
            min(canonical.entity_uuid::text)::uuid AS entity_uuid
        FROM knowledge_relationships AS relationship
        JOIN canonical_names AS canonical
          ON canonical.normalized_name = relationship.normalized_unresolved_name
        WHERE relationship.is_current
          AND NOT relationship.manual_override
          AND relationship.resolution_state IN ('unresolved','ambiguous')
          AND relationship.relationship_type_code IN ('occurs_at_location','mission_occurs_at_location')
        GROUP BY relationship.id
        HAVING count(DISTINCT canonical.entity_uuid) = 1
    )
"""


def _resolve_quest_places() -> None:
    op.execute(_QUEST_PLACE_MATCHES + """
        INSERT INTO knowledge_relationships (
            id, source_entity_id, source_scope, relationship_type_code,
            target_entity_id, target_entity_type_id, unresolved_name,
            normalized_unresolved_name, target_identity, resolution_state,
            confidence, source_provider_id, source_document_id, source_job_id,
            provenance_key, source_context, manual_override, valid_from, is_current
        )
        SELECT gen_random_uuid(), original.source_entity_id, original.source_scope,
            original.relationship_type_code, match.entity_uuid, target.entity_type,
            NULL, NULL, 'entity:' || match.entity_uuid::text, 'resolved', 'high',
            original.source_provider_id, original.source_document_id, original.source_job_id,
            original.provenance_key,
            coalesce(original.source_context, '{}'::jsonb) || jsonb_build_object(
                'resolution_policy', 'exact_name_or_alias_only',
                'resolved_from', original.id::text,
                'previous_resolution_state', original.resolution_state,
                'resolution_migration', 'knowledge_named_places_20260724'
            ), false, now(), true
        FROM exact_matches AS match
        JOIN knowledge_relationships AS original ON original.id = match.relationship_id
        JOIN knowledge_entities AS target ON target.uuid = match.entity_uuid
        ON CONFLICT (
            source_entity_id, source_scope, relationship_type_code,
            target_identity, provenance_key
        ) WHERE is_current DO NOTHING
    """)
    op.execute(_QUEST_PLACE_MATCHES + """
        UPDATE knowledge_relationships AS original
        SET is_current = false, resolution_state = 'superseded', valid_until = now(),
            superseded_by_id = replacement.id, updated_at = now()
        FROM exact_matches AS match
        JOIN knowledge_relationships AS replacement
          ON replacement.target_entity_id = match.entity_uuid AND replacement.is_current
        WHERE original.id = match.relationship_id
          AND replacement.source_entity_id = original.source_entity_id
          AND replacement.source_scope = original.source_scope
          AND replacement.relationship_type_code = original.relationship_type_code
          AND replacement.provenance_key = original.provenance_key
    """)


def upgrade() -> None:
    _register_relationship_types()
    _reclassify_existing_places()
    op.execute("""
        UPDATE knowledge_providers
        SET supports_entities = '["creature","item","quest","npc","location","area","town"]'::jsonb,
            updated_at = now()
        WHERE provider_id = 'tibiawiki'
    """)
    _backfill_named_edges()
    _resolve_quest_places()


def downgrade() -> None:
    op.execute("""
        UPDATE knowledge_relationships AS original
        SET is_current = true,
            resolution_state = coalesce(replacement.source_context->>'previous_resolution_state', 'unresolved'),
            valid_until = NULL, superseded_by_id = NULL, updated_at = now()
        FROM knowledge_relationships AS replacement
        WHERE replacement.source_context->>'resolution_migration' = 'knowledge_named_places_20260724'
          AND replacement.source_context ? 'resolved_from'
          AND original.superseded_by_id = replacement.id
          AND NOT original.manual_override
    """)
    op.execute("""
        DELETE FROM knowledge_relationships
        WHERE source_context->>'resolution_migration' = 'knowledge_named_places_20260724'
    """)
    op.execute("""
        UPDATE knowledge_providers
        SET supports_entities = '["creature","item","quest","npc","location"]'::jsonb,
            updated_at = now()
        WHERE provider_id = 'tibiawiki'
    """)
    op.execute("""
        DELETE FROM knowledge_relationships
        WHERE relationship_type_code IN (
            'located_at','hosts_npc','contained_in','contains',
            'leads_to','destination_of_access'
        )
    """)
    op.execute("""
        DELETE FROM knowledge_relationship_types
        WHERE code IN (
            'located_at','hosts_npc','contained_in','contains',
            'leads_to','destination_of_access'
        )
    """)
