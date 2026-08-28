#!/usr/bin/env python3
"""Audit and repair canonical Quest knowledge through durable jobs.

This tool is deliberately repair-oriented. It never truncates canonical tables,
never invents missing facts, and never bypasses the registered production
adapter. Retained raw Quest documents can be replayed without network access;
a canonical TibiaWiki overview refresh is a separate explicit phase.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from uuid import UUID

from sqlalchemy import func


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal, verify_connection_and_schema  # noqa: E402
from app.knowledge.adapters import KnowledgeAdapterRegistry  # noqa: E402
from app.knowledge.models import (  # noqa: E402
    ACTIVE_KNOWLEDGE_JOB_STATES,
    KnowledgeDocument,
    KnowledgeJob,
    KnowledgeProvider,
    KnowledgeRelationship,
)
from app.knowledge.services import EnqueueKnowledgeJob, KnowledgeJobService  # noqa: E402
from app.models.external_data import TibiaWikiQuest  # noqa: E402


CONFIRMATION = "REPAIR TIBIAHUB QUEST KNOWLEDGE"
TERMINAL_STATES = {"succeeded", "partially_succeeded", "failed", "cancelled"}


def _database_guard() -> None:
    url = settings.database_url
    if (
        url.get_backend_name() != "postgresql"
        or url.database != "tibiahub"
        or url.host not in {"127.0.0.1", "localhost", "::1"}
    ):
        raise SystemExit("Refusing to repair outside local PostgreSQL database tibiahub.")


def _has_text(value: str | None) -> bool:
    return bool(value and value.strip())


def _snapshot(db) -> dict[str, object]:
    quests = db.query(TibiaWikiQuest).order_by(TibiaWikiQuest.id.asc()).all()
    leaf = [quest for quest in quests if not quest.is_group]
    quest_documents = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.provider_id == "tibiawiki",
        KnowledgeDocument.provider_document_id.like("quest:%"),
    )
    spoiler_documents = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.provider_id == "tibiawiki",
        KnowledgeDocument.provider_document_id.like("quest_spoiler:%"),
    )
    job_counts = Counter(
        state
        for (state,) in db.query(KnowledgeJob.state).filter(
            KnowledgeJob.provider_id == "tibiawiki",
            KnowledgeJob.entity_type_id == "quest",
        ).all()
    )
    relationship_counts = Counter(
        state
        for (state,) in db.query(KnowledgeRelationship.resolution_state).filter(
            KnowledgeRelationship.is_current.is_(True),
            KnowledgeRelationship.source_entity.has(entity_type="quest"),
        ).all()
    )
    provider = db.get(KnowledgeProvider, "tibiawiki")
    return {
        "quests_total": len(quests),
        "quests_leaf": len(leaf),
        "with_description_or_summary": sum(
            _has_text(quest.description) or _has_text(quest.summary) for quest in leaf
        ),
        "with_missions": sum(bool(quest.missions) for quest in leaf),
        "with_required_items": sum(bool(quest.required_items) for quest in leaf),
        "with_required_quests": sum(bool(quest.required_quests) for quest in leaf),
        "with_rewarded_items": sum(bool(quest.rewarded_items) for quest in leaf),
        "with_locations": sum(bool(quest.locations) for quest in leaf),
        "with_duration": sum(_has_text(quest.duration) for quest in leaf),
        "retained_quest_documents": quest_documents.count(),
        "distinct_retained_quest_documents": db.query(
            func.count(func.distinct(KnowledgeDocument.provider_document_id))
        ).filter(
            KnowledgeDocument.provider_id == "tibiawiki",
            KnowledgeDocument.provider_document_id.like("quest:%"),
        ).scalar() or 0,
        "retained_spoiler_documents": spoiler_documents.count(),
        "quest_jobs": dict(sorted(job_counts.items())),
        "quest_relationships": dict(sorted(relationship_counts.items())),
        "provider": {
            "enabled": bool(provider and provider.enabled),
            "health": provider.health if provider else "missing",
            "last_success_at": provider.last_success_at.isoformat() if provider and provider.last_success_at else None,
        },
    }


def _latest_document_external_ids(db) -> list[str]:
    rows = db.query(
        KnowledgeDocument.provider_document_id,
        KnowledgeDocument.retrieved_at,
    ).filter(
        KnowledgeDocument.provider_id == "tibiawiki",
        KnowledgeDocument.provider_document_id.like("quest:%"),
    ).order_by(
        KnowledgeDocument.provider_document_id.asc(),
        KnowledgeDocument.retrieved_at.desc(),
    ).all()
    latest: dict[str, object] = {}
    for document_id, retrieved_at in rows:
        prefix, separator, external_id = str(document_id).partition(":")
        if prefix != "quest" or separator != ":" or not external_id.isdigit():
            continue
        latest.setdefault(external_id, retrieved_at)
    return sorted(latest, key=lambda value: int(value))


def _enqueue_replay(db, *, offset: int, limit: int, registry: KnowledgeAdapterRegistry):
    external_ids = _latest_document_external_ids(db)
    selected = external_ids[offset: offset + limit]
    jobs: list[KnowledgeJob] = []
    created = skipped = 0
    for external_id in selected:
        payload = {"external_id": external_id}
        registry.validate_enqueue("tibiawiki", "quest_renormalize", "quest", {}, payload)
        result = KnowledgeJobService.enqueue(
            db,
            EnqueueKnowledgeJob(
                provider_id="tibiawiki",
                job_type="quest_renormalize",
                entity_type="quest",
                payload=payload,
                trigger="renormalize",
                allow_completed_recreate=True,
            ),
        )
        jobs.append(result.job)
        created += int(result.created)
        skipped += int(not result.created)
    return jobs, {
        "available": len(external_ids),
        "offset": offset,
        "selected": len(selected),
        "created": created,
        "already_active": skipped,
        "next_offset": offset + len(selected) if offset + len(selected) < len(external_ids) else None,
    }


def _enqueue_catalog_refresh(
    db,
    *,
    batch_limit: int,
    registry: KnowledgeAdapterRegistry,
    enable_provider: bool,
):
    provider = db.get(KnowledgeProvider, "tibiawiki")
    if provider is None:
        raise SystemExit("TibiaWiki provider is not registered.")
    if enable_provider:
        provider.enabled = True
        if provider.health == "disabled":
            provider.health = "unknown"
        provider.cooldown_until = None
        db.flush()
    if not provider.enabled or provider.health == "disabled":
        raise SystemExit("TibiaWiki provider is disabled. Re-run with --enable-provider if intentional.")

    scope = {"batch_limit": batch_limit}
    registry.validate_enqueue("tibiawiki", "quest_catalog", "quest", scope, {})
    result = KnowledgeJobService.enqueue(
        db,
        EnqueueKnowledgeJob(
            provider_id="tibiawiki",
            job_type="quest_catalog",
            entity_type="quest",
            scope=scope,
            priority=200,
            trigger="manual",
            allow_completed_recreate=True,
        ),
    )
    return result.job, result.created


def _wait_for_correlations(correlation_ids: set[UUID], timeout: int) -> dict[str, int]:
    if not correlation_ids:
        return {}
    deadline = time.monotonic() + timeout
    previous = None
    while time.monotonic() < deadline:
        with SessionLocal() as db:
            rows = db.query(KnowledgeJob).filter(
                KnowledgeJob.correlation_id.in_(correlation_ids)
            ).all()
            counts = Counter(row.state for row in rows)
            signature = tuple(sorted(counts.items()))
            if signature != previous:
                print("repair_states=" + json.dumps(dict(counts), sort_keys=True), flush=True)
                previous = signature
            if rows and not any(row.state in ACTIVE_KNOWLEDGE_JOB_STATES for row in rows):
                return dict(counts)
        time.sleep(3)
    raise SystemExit("Timed out waiting for Quest repair jobs; durable jobs may still be running.")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit/replay/refetch TibiaHub Quest knowledge without destructive reset.",
    )
    parser.add_argument("--replay-existing", action="store_true", help="Replay retained quest:* raw documents.")
    parser.add_argument("--refresh-catalog", action="store_true", help="Refresh canonical Quest Overview catalog and detail children.")
    parser.add_argument("--enable-provider", action="store_true", help="Explicitly enable TibiaWiki for --refresh-catalog.")
    parser.add_argument("--offset", type=int, default=0, help="Deterministic replay offset.")
    parser.add_argument("--limit", type=int, default=100, help="Retained documents to replay in this pass (1-500).")
    parser.add_argument("--batch-limit", type=int, default=50, help="TibiaWiki catalog page size (1-50).")
    parser.add_argument("--wait", action="store_true", help="Wait for all jobs in the queued correlations, including catalog children.")
    parser.add_argument("--wait-timeout", type=int, default=21600)
    parser.add_argument("--confirm", help=f"Exact confirmation required to enqueue: {CONFIRMATION}")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if args.offset < 0 or not 1 <= args.limit <= 500 or not 1 <= args.batch_limit <= 50:
        raise SystemExit("Invalid offset/limit/batch-limit.")

    _database_guard()
    verify_connection_and_schema()
    registry = KnowledgeAdapterRegistry()

    with SessionLocal() as db:
        before = _snapshot(db)
        available = len(_latest_document_external_ids(db))
    print(json.dumps({"mode": "audit", "before": before, "replay_available": available}, indent=2, sort_keys=True))

    mutate = args.replay_existing or args.refresh_catalog or args.enable_provider
    if not mutate:
        print("No repair phase requested; audit only.")
        return 0
    if args.confirm != CONFIRMATION:
        raise SystemExit(f"Repair enqueue requires --confirm '{CONFIRMATION}'")
    if args.enable_provider and not args.refresh_catalog:
        raise SystemExit("--enable-provider is only valid with --refresh-catalog.")

    correlations: set[UUID] = set()
    report: dict[str, object] = {}
    with SessionLocal.begin() as db:
        if args.replay_existing:
            jobs, replay = _enqueue_replay(
                db,
                offset=args.offset,
                limit=args.limit,
                registry=registry,
            )
            correlations.update(job.correlation_id for job in jobs)
            report["replay"] = replay
        if args.refresh_catalog:
            job, created = _enqueue_catalog_refresh(
                db,
                batch_limit=args.batch_limit,
                registry=registry,
                enable_provider=args.enable_provider,
            )
            correlations.add(job.correlation_id)
            report["catalog_refresh"] = {
                "job_id": str(job.id),
                "created": created,
                "batch_limit": args.batch_limit,
            }

    print(json.dumps({"queued": report}, indent=2, sort_keys=True))

    terminal = _wait_for_correlations(correlations, args.wait_timeout) if args.wait else {}
    with SessionLocal() as db:
        after = _snapshot(db)
    print(json.dumps({"terminal_states": terminal, "after": after}, indent=2, sort_keys=True))

    if terminal.get("failed", 0) or terminal.get("cancelled", 0):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
