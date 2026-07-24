#!/usr/bin/env python3
"""Safely resolve one existing TibiaHub graph reference to one existing entity."""

import argparse
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal, verify_connection_and_schema  # noqa: E402
from app.knowledge.models import KnowledgeEntity, KnowledgeRelationship  # noqa: E402
from app.knowledge.registry import RelationshipTypeRegistry  # noqa: E402
from app.knowledge.services import KnowledgeGraphService  # noqa: E402
from app.models.user import User  # noqa: E402
from app.core.permissions import is_global_admin  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--relationship-id", type=UUID, required=True)
    parser.add_argument("--target-entity-id", type=UUID, required=True)
    parser.add_argument("--admin-user-id", type=int, required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-resolve-knowledge-reference", action="store_true")
    args = parser.parse_args()
    if settings.database_name != "tibiahub":
        raise SystemExit("Refusing to mutate a database other than the exact TibiaHub database.")
    if len(args.reason.strip()) < 3:
        raise SystemExit("A meaningful audit reason is required.")
    verify_connection_and_schema()
    with SessionLocal() as db:
        row = db.get(KnowledgeRelationship, args.relationship_id)
        if row is None:
            raise SystemExit("Relationship not found.")
        admin = db.get(User, args.admin_user_id)
        if admin is None or not is_global_admin(admin):
            raise SystemExit("An existing global-admin user is required.")
        # Service validation confirms the target exists and has the allowed type.
        if args.dry_run:
            target = db.get(KnowledgeEntity, args.target_entity_id)
            if target is None:
                raise SystemExit("Resolution target not found.")
            RelationshipTypeRegistry.validate(
                db, row.relationship_type_code, row.source_entity.entity_type, target.entity_type,
            )
            print(f"Dry run valid: relationship={row.id} target_type={target.entity_type}")
            return
        if not args.confirm_resolve_knowledge_reference:
            raise SystemExit("Use --confirm-resolve-knowledge-reference or --dry-run.")
        resolved = KnowledgeGraphService.resolve_reference(
            db, row, args.target_entity_id, admin_id=args.admin_user_id, reason=args.reason.strip(),
        )
        db.commit()
        print(f"Resolved relationship {row.id}; replacement={resolved.id}")


if __name__ == "__main__":
    main()
