#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.db.database import SessionLocal, verify_connection_and_schema
from app.knowledge.models import KnowledgeDocument, KnowledgeJob
from app.knowledge.services import (
    EnqueueKnowledgeJob,
    KnowledgeJobService,
)
from app.models import Creature
from app.services.creature_category_service import (
    resolve_creature_category,
)
from app.services.text_utils import normalize_search_text


TERMINAL = {
    "succeeded",
    "partially_succeeded",
    "failed",
    "cancelled",
}


def unresolved_creatures(db):
    return [
        row
        for row in (
            db.query(Creature)
            .filter(
                Creature.is_hidden == False,
                Creature.is_boss == False,
            )
            .order_by(Creature.id)
            .all()
        )
        if resolve_creature_category(
            bestiary_class=row.bestiary_class,
            creature_class=row.creature_class,
            classification=row.classification,
        )
        is None
    ]


def latest_documents_by_name(db):
    documents = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.provider_id == "tibiawiki",
            KnowledgeDocument.provider_document_id.like(
                "creature:%"
            ),
        )
        .order_by(
            KnowledgeDocument.retrieved_at.desc()
        )
        .all()
    )

    result = {}

    for document in documents:
        external_id = (
            document.provider_document_id
            .split(":", 1)[-1]
            .strip()
        )

        if not external_id.isdigit():
            continue

        metadata = document.document_metadata or {}
        raw = (
            document.raw_json
            if isinstance(document.raw_json, dict)
            else {}
        )
        parsed = (
            raw.get("parse")
            if isinstance(raw.get("parse"), dict)
            else {}
        )

        title = str(
            metadata.get("page_title")
            or parsed.get("title")
            or ""
        ).strip()

        key = normalize_search_text(title)

        if key and key not in result:
            result[key] = external_id

    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm-renormalize-unresolved-creatures",
        action="store_true",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
    )
    parser.add_argument(
        "--wait-timeout",
        type=int,
        default=1800,
    )
    args = parser.parse_args()

    if settings.database_name != "tibiahub":
        raise SystemExit(
            "Refusing to enqueue outside tibiahub."
        )

    if not args.confirm_renormalize_unresolved_creatures:
        raise SystemExit(
            "Use --confirm-renormalize-unresolved-creatures."
        )

    verify_connection_and_schema()

    job_ids = []
    missing = []

    with SessionLocal.begin() as db:
        unresolved = unresolved_creatures(db)
        documents = latest_documents_by_name(db)

        created = 0
        active = 0

        for creature in unresolved:
            external_id = documents.get(
                normalize_search_text(creature.name)
            )

            if not external_id:
                missing.append(creature.name)
                continue

            result = KnowledgeJobService.enqueue(
                db,
                EnqueueKnowledgeJob(
                    provider_id="tibiawiki",
                    job_type="creature_renormalize",
                    entity_type="creature",
                    payload={
                        "external_id": external_id,
                    },
                    trigger="renormalize",
                    allow_completed_recreate=True,
                ),
            )

            job_ids.append(result.job.id)

            if result.created:
                created += 1
            else:
                active += 1

        print(
            f"unresolved_before={len(unresolved)} "
            f"matched={len(job_ids)} "
            f"enqueued={created} "
            f"already_active={active} "
            f"missing_document={len(missing)}"
        )

        if missing:
            print(
                "missing_document_sample="
                + ", ".join(missing[:20])
            )

    if not args.wait or not job_ids:
        return

    deadline = time.monotonic() + args.wait_timeout
    last = None

    while time.monotonic() < deadline:
        with SessionLocal() as db:
            rows = (
                db.query(KnowledgeJob)
                .filter(KnowledgeJob.id.in_(job_ids))
                .all()
            )

            counts = {}
            for row in rows:
                counts[row.state] = (
                    counts.get(row.state, 0) + 1
                )

            signature = tuple(sorted(counts.items()))

            if signature != last:
                print(f"renormalize_states={counts}")
                last = signature

            if rows and all(
                row.state in TERMINAL
                for row in rows
            ):
                break

        time.sleep(2)
    else:
        raise SystemExit(
            "Timed out waiting for renormalization."
        )

    with SessionLocal() as db:
        remaining = unresolved_creatures(db)

        failed = (
            db.query(KnowledgeJob)
            .filter(
                KnowledgeJob.id.in_(job_ids),
                KnowledgeJob.state.in_(
                    ("failed", "cancelled")
                ),
            )
            .count()
        )

        print(
            f"unresolved_after={len(remaining)} "
            f"renormalize_failed={failed}"
        )

        if remaining:
            print(
                "remaining_sample="
                + ", ".join(
                    row.name
                    for row in remaining[:20]
                )
            )

        if failed:
            raise SystemExit(
                "One or more renormalization jobs failed."
            )


if __name__ == "__main__":
    main()
