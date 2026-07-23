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
    parser.add_argument("--canonical-name", required=True)
    parser.add_argument("--language-neutral-id", required=True)
    parser.add_argument("--provider-document-id", required=True)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    if settings.database_name != "tibiahub":
        raise SystemExit("Refusing to enqueue outside the exact TibiaHub database.")
    KnowledgeAdapterRegistry().resolve(args.provider, args.job_type, args.entity_type)
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
                payload={
                    "canonical_name": args.canonical_name,
                    "language_neutral_id": args.language_neutral_id,
                    "provider_document_id": args.provider_document_id,
                },
                trigger="manual",
            ),
        )
        print(f"Knowledge job {'created' if result.created else 'already active'}: id={result.job.id} {summary}")


if __name__ == "__main__":
    main()
