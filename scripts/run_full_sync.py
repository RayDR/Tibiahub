#!/usr/bin/env python3
"""Queue TibiaHub synchronization jobs through the durable sync worker."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from app.db.database import (
    SessionLocal,
    verify_connection_and_schema,
)
from app.services.sync_service import SyncService


TERMINAL_STATES = {
    "completed",
    "completed_with_errors",
    "failed",
    "cancelled",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Queue TibiaHub synchronization jobs and wait for the "
            "durable sync worker to complete them"
        )
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Run full sync",
    )
    parser.add_argument(
        "--creatures",
        action="store_true",
        help="Sync creatures",
    )
    parser.add_argument(
        "--bosses",
        action="store_true",
        help="Sync bosses",
    )
    parser.add_argument(
        "--items",
        action="store_true",
        help="Sync items",
    )
    parser.add_argument(
        "--quests",
        action="store_true",
        help="Sync quests",
    )
    parser.add_argument(
        "--hunt-zones",
        action="store_true",
        help="Sync hunt zones",
    )
    parser.add_argument(
        "--images",
        action="store_true",
        help="Synchronize the local image cache",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force refresh where supported",
    )
    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Resume a failed, cancelled, or partial job",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit processed entities per job",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for segmented sync",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Retry attempts per entity",
    )
    parser.add_argument(
        "--external-timeout",
        type=int,
        default=15,
        help="External request timeout in seconds",
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="Skip images when running --all",
    )
    parser.add_argument(
        "--wait-timeout",
        type=int,
        default=21600,
        help="Maximum seconds to wait for each job",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=3.0,
        help="Seconds between job status checks",
    )

    return parser


def resolve_targets(
    args: argparse.Namespace,
) -> list[str]:
    if args.all:
        return ["full"]

    targets: list[str] = []

    if args.creatures:
        targets.append("creatures")
    if args.bosses:
        targets.append("bosses")
    if args.items:
        targets.append("items")
    if args.quests:
        targets.append("quests")
    if args.hunt_zones:
        targets.append("hunt-zones")
    if args.images:
        targets.append("images")

    return targets or ["full"]


def serialize_job(job: Any) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "target": job.job_type,
        "status": job.status,
        "progress_percent": job.progress_percent or 0,
        "current_step": job.current_step,
        "message": job.message,
        "processed_count": job.processed_count or 0,
        "failed_count": job.failed_count or 0,
        "error": job.error_message or job.error,
        "summary": job.result_summary,
        "checkpoint": job.checkpoint,
        "worker_id": job.worker_id,
    }


def wait_for_job(
    job_id: str,
    *,
    timeout_seconds: int,
    poll_interval: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(1, timeout_seconds)
    last_signature: tuple[Any, ...] | None = None

    while True:
        db = SessionLocal()

        try:
            job = SyncService.get_job(db, job_id)

            if job is None:
                return {
                    "job_id": job_id,
                    "status": "not_found",
                    "error": "Sync job was not found",
                }

            payload = serialize_job(job)
            signature = (
                payload["status"],
                payload["progress_percent"],
                payload["current_step"],
                payload["message"],
                payload["processed_count"],
                payload["failed_count"],
            )

            if signature != last_signature:
                print(
                    json.dumps(
                        payload,
                        ensure_ascii=True,
                    ),
                    flush=True,
                )
                last_signature = signature

            if job.status in TERMINAL_STATES:
                return payload
        finally:
            db.close()

        if time.monotonic() >= deadline:
            return {
                "job_id": job_id,
                "status": "wait_timeout",
                "error": (
                    "The CLI stopped waiting, but the durable job "
                    "may still be running"
                ),
            }

        time.sleep(max(0.5, poll_interval))


def run_target(
    target: str,
    *,
    force: bool,
    skip_images: bool,
    limit: int | None,
    batch_size: int,
    max_retries: int,
    external_timeout: int,
    wait_timeout: int,
    poll_interval: float,
) -> int:
    db = SessionLocal()

    try:
        job = SyncService.create_job(
            db,
            job_type=target,
            requester="cli",
            requested_by_user_id=None,
            job_limit=limit,
            batch_size=batch_size,
            max_retries=max_retries,
            external_timeout_seconds=external_timeout,
            force_refresh=force,
            skip_images=skip_images,
            continue_on_error=True,
            maintenance_requested=False,
            operation_label=f"CLI {target} synchronization",
        )
        job_id = job.id
    finally:
        db.close()

    print(
        json.dumps(
            {
                "job_id": job_id,
                "target": target,
                "status": "queued",
            },
            ensure_ascii=True,
        ),
        flush=True,
    )

    result = wait_for_job(
        job_id,
        timeout_seconds=wait_timeout,
        poll_interval=poll_interval,
    )

    print(
        json.dumps(result, ensure_ascii=True),
        flush=True,
    )

    return 0 if result.get("status") == "completed" else 1


def resume_target(
    job_id: str,
    *,
    wait_timeout: int,
    poll_interval: float,
) -> int:
    db = SessionLocal()

    try:
        job = SyncService.resume_job(db, job_id)

        if job is None:
            print(
                json.dumps(
                    {
                        "job_id": job_id,
                        "status": "not_found",
                        "error": "Sync job was not found",
                    }
                )
            )
            return 1
    except RuntimeError as exc:
        print(
            json.dumps(
                {
                    "job_id": job_id,
                    "status": "invalid_resume",
                    "error": str(exc),
                }
            )
        )
        return 1
    finally:
        db.close()

    result = wait_for_job(
        job_id,
        timeout_seconds=wait_timeout,
        poll_interval=poll_interval,
    )

    print(
        json.dumps(result, ensure_ascii=True),
        flush=True,
    )

    return 0 if result.get("status") == "completed" else 1


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    verify_connection_and_schema()

    if args.resume:
        return resume_target(
            args.resume,
            wait_timeout=args.wait_timeout,
            poll_interval=args.poll_interval,
        )

    exit_code = 0

    for target in resolve_targets(args):
        result = run_target(
            target,
            force=args.force,
            skip_images=args.skip_images,
            limit=args.limit,
            batch_size=args.batch_size,
            max_retries=args.max_retries,
            external_timeout=args.external_timeout,
            wait_timeout=args.wait_timeout,
            poll_interval=args.poll_interval,
        )

        if result != 0:
            exit_code = result
            break

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
