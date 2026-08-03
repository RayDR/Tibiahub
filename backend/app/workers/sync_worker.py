"""Dedicated durable synchronization worker entry point."""

from __future__ import annotations

import logging
import signal
import threading

from app.core.config import settings
from app.db.database import SessionLocal, verify_connection_and_schema
from app.services.maintenance_mode_service import MaintenanceModeService
from app.services.sync_service import SyncService


logger = logging.getLogger("app.sync.worker")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not settings.SYNC_WORKER_ENABLED:
        logger.info("sync_worker_disabled worker_id=%s", settings.SYNC_WORKER_ID)
        return
    verify_connection_and_schema()
    stop = threading.Event()
    for selected_signal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(selected_signal, lambda _signum, _frame: stop.set())

    with SessionLocal() as db:
        recovered = SyncService.recover_stale_running_jobs(db, reason="stale after sync worker recovery")
        released = MaintenanceModeService.reconcile(db)
        SyncService.worker_heartbeat(db, settings.SYNC_WORKER_ID, "idle")
        db.commit()
    if recovered or released:
        logger.warning("sync_worker_reconciled recovered=%s released_holds=%s", len(recovered), len(released))

    while not stop.is_set():
        try:
            with SessionLocal() as db:
                job_id = SyncService.claim_next(db, settings.SYNC_WORKER_ID)
                db.commit()
            if job_id is None:
                stop.wait(settings.SYNC_WORKER_POLL_SECONDS)
                continue
            logger.info("sync_worker_job_claimed worker_id=%s job_id=%s", settings.SYNC_WORKER_ID, job_id)
            SyncService._run_job_sync(job_id, settings.SYNC_WORKER_ID)
        except Exception:
            logger.exception("sync_worker_cycle_failed worker_id=%s", settings.SYNC_WORKER_ID)
            stop.wait(settings.SYNC_WORKER_POLL_SECONDS)

    try:
        with SessionLocal() as db:
            SyncService.worker_heartbeat(db, settings.SYNC_WORKER_ID, "stopping")
            db.commit()
    except Exception:
        logger.warning("sync_worker_stopping_heartbeat_failed worker_id=%s", settings.SYNC_WORKER_ID)


if __name__ == "__main__":
    main()
