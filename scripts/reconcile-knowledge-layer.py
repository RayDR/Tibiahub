#!/usr/bin/env python3
"""Audit or apply the bounded TibiaHub P0 knowledge reconciliation pass."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import func


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal, verify_connection_and_schema  # noqa: E402
from app.knowledge.models import (  # noqa: E402
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeExternalMapping,
    KnowledgeRelationship,
    KnowledgeSearchMetadata,
)
from app.knowledge.services import (  # noqa: E402
    KnowledgeGraphService,
    reconcile_exact_references,
    repair_document_provenance,
)


CONFIRMATION = "APPLY-P0-KNOWLEDGE-CLOSURE"


def _snapshot(db) -> dict:
    entities_by_type = {
        entity_type: count
        for entity_type, count in (
            db.query(KnowledgeEntity.entity_type, func.count(KnowledgeEntity.uuid))
            .group_by(KnowledgeEntity.entity_type)
            .order_by(KnowledgeEntity.entity_type)
            .all()
        )
    }
    documents_by_provider = {
        provider_id: count
        for provider_id, count in (
            db.query(KnowledgeDocument.provider_id, func.count(KnowledgeDocument.uuid))
            .group_by(KnowledgeDocument.provider_id)
            .order_by(KnowledgeDocument.provider_id)
            .all()
        )
    }
    mappings_by_provider_type = {
        f"{provider_id}:{entity_type}": count
        for provider_id, entity_type, count in (
            db.query(
                KnowledgeExternalMapping.provider_id,
                KnowledgeExternalMapping.entity_type_id,
                func.count(KnowledgeExternalMapping.id),
            )
            .group_by(
                KnowledgeExternalMapping.provider_id,
                KnowledgeExternalMapping.entity_type_id,
            )
            .order_by(
                KnowledgeExternalMapping.provider_id,
                KnowledgeExternalMapping.entity_type_id,
            )
            .all()
        )
    }
    unresolved = {
        f"{relationship_type}:{target_type}": count
        for relationship_type, target_type, count in (
            db.query(
                KnowledgeRelationship.relationship_type_code,
                KnowledgeRelationship.target_entity_type_id,
                func.count(KnowledgeRelationship.id),
            )
            .filter(
                KnowledgeRelationship.is_current.is_(True),
                KnowledgeRelationship.resolution_state.in_(("unresolved", "ambiguous")),
            )
            .group_by(
                KnowledgeRelationship.relationship_type_code,
                KnowledgeRelationship.target_entity_type_id,
            )
            .order_by(
                KnowledgeRelationship.relationship_type_code,
                KnowledgeRelationship.target_entity_type_id,
            )
            .all()
        )
    }
    return {
        "entities": db.query(KnowledgeEntity).count(),
        "entities_by_type": entities_by_type,
        "raw_documents": db.query(KnowledgeDocument).count(),
        "raw_documents_by_provider": documents_by_provider,
        "raw_documents_unlinked": db.query(KnowledgeDocument).filter(
            KnowledgeDocument.entity_uuid.is_(None)
        ).count(),
        "external_mappings": db.query(KnowledgeExternalMapping).count(),
        "external_mappings_by_provider_type": mappings_by_provider_type,
        "entities_missing_search_metadata": (
            db.query(KnowledgeEntity)
            .outerjoin(
                KnowledgeSearchMetadata,
                KnowledgeSearchMetadata.entity_uuid == KnowledgeEntity.uuid,
            )
            .filter(KnowledgeSearchMetadata.entity_uuid.is_(None))
            .count()
        ),
        "relationships": db.query(KnowledgeRelationship).count(),
        "current_relationships": db.query(KnowledgeRelationship).filter_by(is_current=True).count(),
        "current_unresolved_relationships": sum(unresolved.values()),
        "current_provider_relationships_missing_document": (
            db.query(KnowledgeRelationship)
            .filter(
                KnowledgeRelationship.is_current.is_(True),
                KnowledgeRelationship.source_provider_id.isnot(None),
                KnowledgeRelationship.source_document_id.is_(None),
            )
            .count()
        ),
        "unresolved_by_type": unresolved,
        "graph_consistency": KnowledgeGraphService.verify_consistency(db),
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconcile exact local references and deterministic raw-document provenance"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", help=f"Required exact phrase for --apply: {CONFIRMATION}")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    url = settings.database_url
    if (
        url.get_backend_name() != "postgresql"
        or url.database != "tibiahub"
        or url.host not in {"127.0.0.1", "localhost", "::1"}
    ):
        raise SystemExit("Refusing to reconcile outside local PostgreSQL database tibiahub.")
    if args.apply and args.confirm != CONFIRMATION:
        raise SystemExit(f"--apply requires --confirm {CONFIRMATION}")

    verify_connection_and_schema()
    with SessionLocal() as db:
        before = _snapshot(db)
        exact = reconcile_exact_references(db, apply=args.apply)
        provenance = repair_document_provenance(db, apply=args.apply)
        second_exact = None
        second_provenance = None
        if args.apply:
            second_exact = reconcile_exact_references(db, apply=True)
            second_provenance = repair_document_provenance(db, apply=True)
            db.commit()
        else:
            db.rollback()
        after = _snapshot(db)

    report = {
        "mode": "apply" if args.apply else "dry-run",
        "policy": {
            "resolution": "one exact canonical name or approved alias only",
            "provenance": "existing provider document identity only",
            "deletions": 0,
            "invented_values": 0,
        },
        "before": before,
        "reconciliation": exact.as_dict(),
        "provenance": provenance.as_dict(),
        "second_pass": (
            {
                "reconciliation": second_exact.as_dict(),
                "provenance": second_provenance.as_dict(),
            }
            if second_exact is not None and second_provenance is not None
            else None
        ),
        "after": after,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.apply:
        assert second_exact is not None and second_provenance is not None
        second_mutations = (
            second_exact.resolved
            + second_provenance.relationships_repaired
            + second_provenance.spatial_routes_repaired
        )
        if second_mutations:
            return 1
        consistency = after["graph_consistency"]
        problem_count = sum(
            value
            for key, value in consistency.items()
            if key not in {"relationships", "registry_errors"} and isinstance(value, int)
        )
        if problem_count or consistency["registry_errors"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
