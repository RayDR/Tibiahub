#!/usr/bin/env python3
"""Re-normalize selected retained quest documents without provider access."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.db.database import SessionLocal, verify_connection_and_schema
from app.knowledge.adapters import KnowledgeDocumentDTO, KnowledgeNormalizationContext, TibiaWikiQuestAdapter
from app.knowledge.dto import QuestKnowledgeDTO
from app.knowledge.models import KnowledgeDocument
from app.knowledge.services.normalization import KnowledgeNormalizationService


def _document_id(value: str) -> str:
    prefix, separator, external_id = value.partition(":")
    if prefix != "quest" or separator != ":" or not external_id.isdigit():
        raise argparse.ArgumentTypeError("document IDs must use quest:<numeric-external-id>")
    return value


def _dto(row: KnowledgeDocument) -> KnowledgeDocumentDTO:
    return KnowledgeDocumentDTO(
        provider_code=row.provider_id,
        provider_document_id=row.provider_document_id,
        raw_json=row.raw_json,
        version=row.version,
        etag=row.etag,
        language=row.language,
        metadata=dict(row.document_metadata or {}),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run or apply focused quest re-normalization from immutable local documents.",
    )
    parser.add_argument("--document-id", action="append", required=True, type=_document_id)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply idempotent normalization. Without this flag the command is report-only.",
    )
    args = parser.parse_args()

    if args.execute and settings.database_name != "tibiahub":
        raise SystemExit("Refusing to modify a database other than tibiahub.")

    verify_connection_and_schema()
    adapter = TibiaWikiQuestAdapter()
    report: list[dict[str, object]] = []

    with SessionLocal() as db:
        for document_id in dict.fromkeys(args.document_id):
            row = (
                db.query(KnowledgeDocument)
                .filter_by(provider_id="tibiawiki", provider_document_id=document_id)
                .order_by(KnowledgeDocument.retrieved_at.desc())
                .first()
            )
            if row is None:
                report.append({"document_id": document_id, "status": "missing"})
                continue

            context = KnowledgeNormalizationContext(
                job_id=uuid4(),
                attempt_id=uuid4(),
                correlation_id=uuid4(),
                provider_code="tibiawiki",
                entity_type="quest",
            )
            normalized = adapter.normalize(_dto(row), context)
            item: dict[str, object] = {
                "document_id": document_id,
                "retrieved_at": row.retrieved_at.isoformat(),
                "normalization_action": normalized.action,
                "warnings": list(normalized.warnings),
            }
            if normalized.canonical_data is not None:
                quest = QuestKnowledgeDTO.from_canonical_data(normalized.canonical_data)
                item["quest"] = quest.canonical_name
                item["access_unlocks"] = [
                    {
                        "name": access.name,
                        "destination_name": access.destination_name,
                        "description": access.description,
                    }
                    for access in quest.access_unlocks
                ]
                if args.execute:
                    applied = KnowledgeNormalizationService.apply(db, normalized)
                    item["applied_status"] = applied.status
                    item["metrics"] = applied.metrics
            report.append(item)

        if args.execute:
            db.commit()
        else:
            db.rollback()

    print(json.dumps({"mode": "execute" if args.execute else "dry-run", "documents": report}, indent=2))


if __name__ == "__main__":
    main()
