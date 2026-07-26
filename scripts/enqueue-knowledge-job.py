#!/usr/bin/env python3
"""Safely enqueue one explicitly supported TibiaHub knowledge job."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal, verify_connection_and_schema  # noqa: E402
from app.knowledge.adapters import KnowledgeAdapterRegistry  # noqa: E402
from app.knowledge.services import EnqueueKnowledgeJob, KnowledgeJobService  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-enqueue-knowledge-job", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--job-type", required=True)
    parser.add_argument("--entity-type", required=True)
    parser.add_argument("--canonical-name")
    parser.add_argument("--language-neutral-id")
    parser.add_argument("--provider-document-id")
    parser.add_argument("--external-id")
    parser.add_argument("--creature-name")
    parser.add_argument("--item-name")
    parser.add_argument("--quest-name")
    parser.add_argument("--npc-name")
    parser.add_argument("--location-name")
    parser.add_argument("--batch-limit", type=int)
    parser.add_argument("--confirm-catalog-sync", action="store_true")
    parser.add_argument("--allow-completed-recreate", action="store_true")
    return parser.parse_args()


def request_values(args: argparse.Namespace) -> tuple[dict, dict]:
    if args.job_type in {"creature_catalog", "item_catalog", "quest_catalog", "npc_catalog", "location_catalog"}:
        if not args.confirm_catalog_sync:
            raise SystemExit("Catalog jobs require --confirm-catalog-sync.")
        if args.batch_limit is None:
            raise SystemExit("Catalog jobs require an explicit --batch-limit.")
        return {"batch_limit": args.batch_limit}, {}
    if args.job_type in {"creature_detail", "creature_renormalize"}:
        return {}, {
            key: value
            for key, value in {
                "external_id": args.external_id,
                "page_title": args.creature_name,
            }.items()
            if value
        }
    if args.job_type in {"item_detail", "item_renormalize"}:
        return {}, {
            key: value
            for key, value in {
                "external_id": args.external_id,
                "page_title": args.item_name,
            }.items()
            if value
        }
    if args.job_type in {"quest_detail", "quest_renormalize"}:
        return {}, {
            key: value
            for key, value in {
                "external_id": args.external_id,
                "page_title": args.quest_name,
            }.items()
            if value
        }
    if args.job_type in {"npc_detail", "npc_renormalize"}:
        return {}, {
            key: value
            for key, value in {"external_id": args.external_id, "page_title": args.npc_name}.items()
            if value
        }
    if args.job_type in {"location_detail", "location_renormalize"}:
        return {}, {
            key: value
            for key, value in {"external_id": args.external_id, "page_title": args.location_name}.items()
            if value
        }
    return {}, {
        key: value
        for key, value in {
            "canonical_name": args.canonical_name,
            "language_neutral_id": args.language_neutral_id,
            "provider_document_id": args.provider_document_id,
        }.items()
        if value
    }


def main() -> None:
    args = arguments()
    if settings.database_name != "tibiahub":
        raise SystemExit("Refusing to enqueue outside the exact TibiaHub database.")
    scope, payload = request_values(args)
    registry = KnowledgeAdapterRegistry()
    registry.validate_enqueue(args.provider, args.job_type, args.entity_type, scope, payload)
    summary = f"provider={args.provider} job_type={args.job_type} entity_type={args.entity_type}"
    if args.dry_run:
        print(f"Dry run valid: {summary}")
        return
    if not args.confirm_enqueue_knowledge_job:
        raise SystemExit("Use --confirm-enqueue-knowledge-job or --dry-run.")
    verify_connection_and_schema()
    with SessionLocal.begin() as db:
        result = KnowledgeJobService.enqueue(
            db,
            EnqueueKnowledgeJob(
                provider_id=args.provider,
                job_type=args.job_type,
                entity_type=args.entity_type,
                scope=scope,
                payload=payload,
                trigger="manual",
                allow_completed_recreate=args.allow_completed_recreate,
            ),
        )
        print(f"Knowledge job {'created' if result.created else 'already active'}: id={result.job.id} {summary}")


if __name__ == "__main__":
    main()
