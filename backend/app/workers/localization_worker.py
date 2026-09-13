"""Isolated durable content-localization worker entry point."""

from __future__ import annotations

import logging
import signal
import threading

from app.core.config import settings
from app.db.database import SessionLocal, verify_connection_and_schema
from app.localization.queue import LocalizationQueueService


logger = logging.getLogger("app.localization.worker")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not settings.LOCALIZATION_WORKER_ENABLED:
        logger.info("localization_worker_disabled worker_id=%s", settings.LOCALIZATION_WORKER_ID)
        return
    if not settings.LOCALIZATION_ENABLED:
        logger.warning("localization_worker_feature_disabled worker_id=%s", settings.LOCALIZATION_WORKER_ID)
        return
    verify_connection_and_schema()
    stop = threading.Event()
    for selected_signal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(selected_signal, lambda _signum, _frame: stop.set())
    while not stop.is_set():
        try:
            processed = LocalizationQueueService.process_one(worker_id=settings.LOCALIZATION_WORKER_ID)
            stop.wait(0.1 if processed else settings.LOCALIZATION_WORKER_POLL_SECONDS)
        except Exception:
            logger.exception("localization_worker_cycle_failed worker_id=%s", settings.LOCALIZATION_WORKER_ID)
            stop.wait(settings.LOCALIZATION_WORKER_POLL_SECONDS)
    try:
        with SessionLocal.begin() as db:
            LocalizationQueueService.heartbeat(db, settings.LOCALIZATION_WORKER_ID, state="stopping")
    except Exception:
        logger.warning("localization_worker_stopping_heartbeat_failed worker_id=%s", settings.LOCALIZATION_WORKER_ID)


if __name__ == "__main__":
    main()
