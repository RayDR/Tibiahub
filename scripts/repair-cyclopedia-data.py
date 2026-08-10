#!/usr/bin/env python3

from __future__ import annotations

import argparse
import time
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.db.database import (
    SessionLocal,
    verify_connection_and_schema,
)
from app.knowledge.models import KnowledgeJob
from app.services.creature_recovery_service import (
    build_category_recovery_plan,
    category_coverage,
    clear_legacy_beast_classifications,
    enqueue_category_recovery,
    hide_non_creature_catalog_rows,
    latest_creature_documents_by_name,
    list_unresolved_creatures,
    remove_malformed_loot,
)
from app.services.text_utils import normalize_search_text


TERMINAL_STATES = {
    "succeeded",
    "partially_succeeded",
    "failed",
    "cancelled",
}


def print_coverage(
    label: str,
    coverage: dict,
) -> None:
    print(
        f"{label}_total={coverage['total']} "
        f"{label}_categorized={coverage['categorized']} "
        f"{label}_unresolved={coverage['unresolved']} "
        f"{label}_coverage_percent="
        f"{coverage['coverage_percent']:.2f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--confirm-repair-cyclopedia-data",
        action="store_true",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
    )
    parser.add_argument(
        "--wait-timeout",
        type=int,
        default=21600,
    )

    args = parser.parse_args()

    if settings.database_name != "tibiahub":
        raise SystemExit(
            "Refusing to modify a database other than tibiahub."
        )

    verify_connection_and_schema()

    with SessionLocal() as db:
        before = category_coverage(db)
        plan = build_category_recovery_plan(db)

    renormalize_count = sum(
        1 for row in plan
        if row.mode == "renormalize"
    )
    detail_count = sum(
        1 for row in plan
        if row.mode == "detail"
    )

    print_coverage("before", before)
    print(
        f"recovery_plan_total={len(plan)} "
        f"recovery_plan_renormalize={renormalize_count} "
        f"recovery_plan_detail_fetch={detail_count}"
    )

    if not args.confirm_repair_cyclopedia_data:
        print(
            "dry_run=true "
            "use --confirm-repair-cyclopedia-data "
            "to apply repairs"
        )
        return 0

    with SessionLocal.begin() as db:
        non_creature_pages_hidden = (
            hide_non_creature_catalog_rows(db)
        )

        legacy_beast_cleared = (
            clear_legacy_beast_classifications(db)
        )

        (
            malformed_loot_removed,
            malformed_loot_creatures,
        ) = remove_malformed_loot(db)

        # Rebuild after cleaning legacy classification because
        # Beast rows remain intentionally unresolved.
        plan = build_category_recovery_plan(db)

        enqueue_result = enqueue_category_recovery(
            db,
            plan,
        )

    print(
        f"non_creature_pages_hidden="
        f"{non_creature_pages_hidden} "
        f"legacy_beast_cleared={legacy_beast_cleared} "
        f"malformed_loot_removed={malformed_loot_removed} "
        f"malformed_loot_affected_creatures="
        f"{malformed_loot_creatures}"
    )

    print(
        f"recovery_jobs_total={enqueue_result.total} "
        f"recovery_jobs_renormalize="
        f"{enqueue_result.renormalize} "
        f"recovery_jobs_detail_fetch="
        f"{enqueue_result.detail} "
        f"recovery_jobs_created="
        f"{enqueue_result.created} "
        f"recovery_jobs_already_active="
        f"{enqueue_result.already_active}"
    )

    if (
        not args.wait
        or not enqueue_result.job_ids
    ):
        return 0

    deadline = (
        time.monotonic()
        + args.wait_timeout
    )
    last_signature = None

    while time.monotonic() < deadline:
        with SessionLocal() as db:
            rows = (
                db.query(KnowledgeJob)
                .filter(
                    KnowledgeJob.id.in_(
                        enqueue_result.job_ids
                    )
                )
                .all()
            )

            counts = Counter(
                row.state
                for row in rows
            )

            signature = tuple(
                sorted(counts.items())
            )

            if signature != last_signature:
                print(
                    "recovery_states="
                    + str(dict(counts))
                )
                last_signature = signature

            if (
                len(rows)
                == len(
                    set(
                        enqueue_result.job_ids
                    )
                )
                and all(
                    row.state
                    in TERMINAL_STATES
                    for row in rows
                )
            ):
                break

        time.sleep(5)
    else:
        raise SystemExit(
            "Timed out waiting for creature recovery jobs."
        )

    with SessionLocal() as db:
        final_jobs = (
            db.query(KnowledgeJob)
            .filter(
                KnowledgeJob.id.in_(
                    enqueue_result.job_ids
                )
            )
            .all()
        )

        final_states = Counter(
            row.state
            for row in final_jobs
        )

        after = category_coverage(db)
        unresolved = list_unresolved_creatures(db)
        documents = (
            latest_creature_documents_by_name(db)
        )

        linked = sum(
            1
            for row in unresolved
            if row.knowledge_entity_id
            is not None
        )

        stored_match = sum(
            1
            for row in unresolved
            if normalize_search_text(row.name)
            in documents
        )

        by_class = Counter(
            str(
                row.creature_class
                or "<missing>"
            )
            for row in unresolved
        )

    print(
        "recovery_final_states="
        + str(dict(final_states))
    )

    print_coverage("after", after)

    print(
        f"remaining_unresolved_linked={linked} "
        f"remaining_unresolved_with_stored_document="
        f"{stored_match} "
        f"remaining_unresolved_without_stored_document="
        f"{len(unresolved) - stored_match}"
    )

    print(
        "remaining_unresolved_by_class="
        + str(dict(by_class.most_common()))
    )

    failed = (
        final_states.get("failed", 0)
        + final_states.get(
            "cancelled",
            0,
        )
    )

    print(
        f"recovery_failed_or_cancelled={failed}"
    )

    if unresolved:
        print(
            "remaining_unresolved_sample="
            + ", ".join(
                row.name
                for row in unresolved[:30]
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
