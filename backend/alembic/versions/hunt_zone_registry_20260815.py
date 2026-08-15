"""Align Hunt Zone relationship registry with runtime definitions.

Revision ID: hunt_zone_registry_20260815
Revises: provider_knowledge_20260813
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision = "hunt_zone_registry_20260815"
down_revision = "provider_knowledge_20260813"
branch_labels = None
depends_on = None


RELATIONSHIP_TYPES = (
    ("appears_in", "has_creature", ["creature", "boss"], ["area", "location", "hunt_zone"]),
    ("has_creature", "appears_in", ["area", "location", "hunt_zone"], ["creature", "boss"]),
    (
        "located_at",
        "hosts_npc",
        ["creature", "item", "quest", "npc", "boss", "hunt_zone", "access"],
        ["area", "town", "location"],
    ),
    (
        "hosts_npc",
        "located_at",
        ["area", "town", "location"],
        ["creature", "item", "quest", "npc", "boss", "hunt_zone", "access"],
    ),
    ("requires_hunt_quest", "required_for_hunt", ["hunt_zone"], ["quest"]),
    ("required_for_hunt", "requires_hunt_quest", ["quest"], ["hunt_zone"]),
    ("requires_access", "access_for_hunt", ["hunt_zone"], ["access"]),
    ("access_for_hunt", "requires_access", ["access"], ["hunt_zone"]),
)


def upgrade() -> None:
    # Insert with a self-inverse first so the self-referential FK is always
    # satisfied, then connect the real inverse in a second pass.
    for code, _inverse, sources, targets in RELATIONSHIP_TYPES:
        op.execute(sa.text("""
            INSERT INTO knowledge_relationship_types (
                code,
                display_translation_key,
                inverse_code,
                source_entity_types,
                target_entity_types,
                directional,
                "symmetric",
                transitive,
                user_visible,
                ai_visible,
                active
            ) VALUES (
                :code,
                :translation,
                :code,
                CAST(:sources AS jsonb),
                CAST(:targets AS jsonb),
                true,
                false,
                false,
                true,
                true,
                true
            )
            ON CONFLICT (code) DO UPDATE SET
                display_translation_key = EXCLUDED.display_translation_key,
                source_entity_types = EXCLUDED.source_entity_types,
                target_entity_types = EXCLUDED.target_entity_types,
                directional = EXCLUDED.directional,
                "symmetric" = EXCLUDED."symmetric",
                transitive = EXCLUDED.transitive,
                user_visible = EXCLUDED.user_visible,
                ai_visible = EXCLUDED.ai_visible,
                active = true,
                updated_at = now()
        """).bindparams(
            code=code,
            translation=f"knowledgeGraph.relationships.{code}",
            sources=json.dumps(sources),
            targets=json.dumps(targets),
        ))

    for code, inverse, _sources, _targets in RELATIONSHIP_TYPES:
        op.execute(sa.text("""
            UPDATE knowledge_relationship_types
            SET inverse_code = :inverse,
                updated_at = now()
            WHERE code = :code
        """).bindparams(code=code, inverse=inverse))


def downgrade() -> None:
    # Registry rows can be referenced by canonical graph facts after this
    # migration. Removing or narrowing them during downgrade could invalidate
    # durable knowledge, so the data alignment is intentionally retained.
    pass
