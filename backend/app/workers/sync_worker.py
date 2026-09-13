"""Dedicated durable synchronization worker entry point."""

from __future__ import annotations

import logging
import signal
import threading

from app.core.config import settings
from app.db.database import SessionLocal, verify_connection_and_schema
from app.localization.queue import LocalizationQueueService
from app.services.maintenance_mode_service import MaintenanceModeService
from app.services.sync_service import SyncService


logger = logging.getLogger("app.sync.worker")
localization_logger = logging.getLogger("app.localization.worker")


def _localization_lane(stop: threading.Event) -> None:
    """Process translation jobs independently inside the managed worker process.

    The lane has its own database sessions/leases/heartbeat and never executes
    inside canonical sync transactions. A provider failure is contained here
    and cannot terminate or roll back the synchronization lane.
    """
    worker_id = settings.LOCALIZATION_WORKER_ID
    localization_logger.info("localization_lane_started worker_id=%s", worker_id)
    while not stop.is_set():
        try:
            processed = LocalizationQueueService.process_one(worker_id=worker_id)
            stop.wait(0.1 if processed else settings.LOCALIZATION_WORKER_POLL_SECONDS)
        except Exception:
            localization_logger.exception("localization_worker_cycle_failed worker_id=%s", worker_id)
            stop.wait(settings.LOCALIZATION_WORKER_POLL_SECONDS)
    try:
        with SessionLocal.begin() as db:
            LocalizationQueueService.heartbeat(db, worker_id, state="stopping")
    except Exception:
        localization_logger.warning("localization_worker_stopping_heartbeat_failed worker_id=%s", worker_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not settings.SYNC_WORKER_ENABLED:
        logger.info("sync_worker_disabled worker_id=%s", settings.SYNC_WORKER_ID)
        return
    verify_connection_and_schema()
    stop = threading.Event()
    for selected_signal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(selected_signal, lambda _signum, _frame: stop.set())

    localization_thread: threading.Thread | None = None
    if settings.LOCALIZATION_ENABLED and settings.LOCALIZATION_WORKER_ENABLED:
        localization_thread = threading.Thread(
            target=_localization_lane,
            args=(stop,),
            name="tibiahub-localization-lane",
            daemon=True,
        )
        localization_thread.start()
    else:
        localization_logger.info(
            "localization_lane_disabled enabled=%s worker_enabled=%s",
            settings.LOCALIZATION_ENABLED,
            settings.LOCALIZATION_WORKER_ENABLED,
        )

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

    if localization_thread is not None:
        localization_thread.join(timeout=max(5, settings.LOCALIZATION_TIMEOUT_SECONDS + 5))

    try:
        with SessionLocal() as db:
            SyncService.worker_heartbeat(db, settings.SYNC_WORKER_ID, "stopping")
            db.commit()
    except Exception:
        logger.warning("sync_worker_stopping_heartbeat_failed worker_id=%s", settings.SYNC_WORKER_ID)


if __name__ == "__main__":
    main()
