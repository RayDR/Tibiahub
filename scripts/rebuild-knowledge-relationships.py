#!/usr/bin/env python3
"""Idempotently bridge existing TibiaHub compatibility facts into the graph."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal, verify_connection_and_schema  # noqa: E402
from app.knowledge.models import KnowledgeCreatureItemDrop, KnowledgeQuestRelation  # noqa: E402
from app.knowledge.services import KnowledgeGraphService, RelationshipInput  # noqa: E402


QUEST_TYPE_MAP = {"unlocks_quest": "prerequisite_for", "involves_npc": "references_npc"}


def inputs(db):
    for row in db.query(KnowledgeCreatureItemDrop).yield_per(250):
        if row.creature_entity_uuid:
            yield RelationshipInput(
                source_entity_id=row.creature_entity_uuid, relationship_type="drops",
                target_entity_id=row.item_entity_uuid if row.resolution_status == "resolved" else None,
                target_entity_type="item", unresolved_name=None if row.resolution_status == "resolved" else row.item_name,
                resolution_state=row.resolution_status, confidence="high", source_provider_id=row.provider_id,
                source_document_ref=(row.source_document_ids or [None])[-1],
                source_context={"compatibility_table": "knowledge_creature_item_drops"},
            )
        elif row.item_entity_uuid:
            yield RelationshipInput(
                source_entity_id=row.item_entity_uuid, relationship_type="dropped_by",
                target_entity_type="creature", unresolved_name=row.creature_name,
                resolution_state=row.resolution_status, confidence="high", source_provider_id=row.provider_id,
                source_document_ref=(row.source_document_ids or [None])[-1],
                source_context={"compatibility_table": "knowledge_creature_item_drops"},
            )
    for row in db.query(KnowledgeQuestRelation).yield_per(250):
        code = QUEST_TYPE_MAP.get(row.relation_type, row.relation_type)
        if row.mission_id and not code.startswith("mission_"):
            code = f"mission_{code}"
        yield RelationshipInput(
            source_entity_id=row.quest_entity_uuid, source_scope=row.scope_key,
            relationship_type=code, target_entity_id=row.target_entity_uuid,
            target_entity_type=row.target_entity_type,
            unresolved_name=None if row.resolution_status == "resolved" else row.target_name,
            resolution_state=row.resolution_status, confidence="high", source_provider_id=row.provider_id,
            source_document_ref=(row.source_document_ids or [None])[-1],
            source_context={"compatibility_table": "knowledge_quest_relations"}, manual_override=row.protected,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-rebuild-knowledge-relationships", action="store_true")
    args = parser.parse_args()
    if settings.database_name != "tibiahub":
        raise SystemExit("Refusing to rebuild outside the exact TibiaHub database.")
    if not args.dry_run and not args.confirm_rebuild_knowledge_relationships:
        raise SystemExit("Use --confirm-rebuild-knowledge-relationships or --dry-run.")
    verify_connection_and_schema()
    with SessionLocal() as db:
        values = list(inputs(db))
        if args.dry_run:
            print(f"Dry run: {len(values)} compatibility facts are eligible for idempotent bridging.")
            return
        created = changed = 0
        for value in values:
            result = KnowledgeGraphService.upsert(db, value)
            created += int(result.created); changed += int(result.changed)
        db.commit()
        print(f"Rebuild complete: considered={len(values)} created={created} changed={changed}")


if __name__ == "__main__":
    main()
