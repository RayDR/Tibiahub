#!/usr/bin/env python3
"""Credential-free schema and worker-state verification."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal, verify_connection_and_schema  # noqa: E402
import app.models  # noqa: E402,F401  # Register every relationship target before mapper configuration.
from app.knowledge.models import KnowledgeJob, KnowledgeProvider, KnowledgeWorkerHeartbeat  # noqa: E402


def main() -> None:
    if settings.database_name != "tibiahub":
        raise SystemExit("Refusing to verify outside the exact TibiaHub database.")
    verify_connection_and_schema()
    stale_before = datetime.now(UTC) - timedelta(seconds=settings.KNOWLEDGE_WORKER_MAX_IDLE_SECONDS * 2)
    with SessionLocal() as db:
        providers = db.query(KnowledgeProvider).count()
        active = db.query(KnowledgeJob).filter(KnowledgeJob.state.in_(("pending", "claimed", "running", "retrying"))).count()
        failed = db.query(KnowledgeJob).filter(KnowledgeJob.state == "failed").count()
        workers = db.query(KnowledgeWorkerHeartbeat).count()
        stale = db.query(KnowledgeWorkerHeartbeat).filter(KnowledgeWorkerHeartbeat.last_seen_at < stale_before).count()
    print(
        "Knowledge worker verification passed: "
        f"providers={providers} active_jobs={active} failed_jobs={failed} workers={workers} stale_workers={stale}"
    )


if __name__ == "__main__":
    main()
