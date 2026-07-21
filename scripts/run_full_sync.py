#!/usr/bin/env python3
"""Run TibiaHub synchronization jobs from CLI using the shared SyncService."""
from __future__ import annotations

import argparse
import json
import sys

from app.db.database import SessionLocal, init_db
from app.services.sync_service import SyncService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run TibiaHub sync jobs")
    parser.add_argument("--all", action="store_true", help="Run full sync")
    parser.add_argument("--creatures", action="store_true", help="Sync creatures")
    parser.add_argument("--bosses", action="store_true", help="Sync bosses")
    parser.add_argument("--items", action="store_true", help="Sync items")
    parser.add_argument("--quests", action="store_true", help="Sync quests")
    parser.add_argument("--hunt-zones", action="store_true", help="Sync hunt zones")
    parser.add_argument("--images", action="store_true", help="Sync image cache")
    parser.add_argument("--force", action="store_true", help="Force overwrite mode when applicable")
    parser.add_argument("--resume", type=str, default=None, help="Resume from failed/cancelled job id")
    parser.add_argument("--limit", type=int, default=None, help="Limit processed entities per segment")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for segmented sync")
    parser.add_argument("--max-retries", type=int, default=3, help="Retry attempts per entity")
    parser.add_argument("--external-timeout", type=int, default=15, help="Timeout per external request in seconds")
    parser.add_argument("--skip-images", action="store_true", help="Skip image segment when running --all")
    return parser


def resolve_targets(args: argparse.Namespace) -> list[str]:
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


def run_target(
    target: str,
    *,
    force: bool,
    skip_images: bool,
    limit: int | None,
    batch_size: int,
    max_retries: int,
    external_timeout: int,
) -> int:
    db = SessionLocal()
    try:
        job = SyncService.create_job(
            db,
            job_type=target,
            requester="cli",
            job_limit=limit,
            batch_size=batch_size,
            max_retries=max_retries,
            external_timeout_seconds=external_timeout,
        )
        SyncService._run_job_sync(job.id, force, skip_images, limit)
        db.refresh(job)
        print(json.dumps({
            "job_id": job.id,
            "target": target,
            "status": job.status,
            "message": job.message,
            "error": job.error_message or job.error,
            "summary": job.result_summary,
        }, ensure_ascii=True))
        return 0 if job.status == "completed" else 1
    finally:
        db.close()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    init_db()

    if args.resume:
        db = SessionLocal()
        try:
            job = SyncService.resume_job(db, args.resume)
            if not job:
                print(json.dumps({"error": "job not found", "job_id": args.resume}, ensure_ascii=True))
                return 1
            SyncService._run_job_sync(job.id, args.force, args.skip_images, args.limit, True)
            db.refresh(job)
            print(json.dumps({
                "job_id": job.id,
                "target": job.job_type,
                "status": job.status,
                "message": job.message,
                "error": job.error_message or job.error,
                "summary": job.result_summary,
                "checkpoint": job.checkpoint,
            }, ensure_ascii=True))
            return 0 if job.status == "completed" else 1
        except RuntimeError as exc:
            print(json.dumps({"error": str(exc), "job_id": args.resume}, ensure_ascii=True))
            return 1
        finally:
            db.close()

    targets = resolve_targets(args)
    exit_code = 0
    for target in targets:
        rc = run_target(
            target,
            force=args.force,
            skip_images=args.skip_images,
            limit=args.limit,
            batch_size=args.batch_size,
            max_retries=args.max_retries,
            external_timeout=args.external_timeout,
        )
        if rc != 0:
            exit_code = rc
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
