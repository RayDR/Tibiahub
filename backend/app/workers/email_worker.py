"""Isolated durable email worker entry point."""

from __future__ import annotations

import logging
import signal
import threading

from app.core.config import settings
from app.db.database import SessionLocal, verify_connection_and_schema
from app.services.email_outbox_service import EmailOutboxService


logger = logging.getLogger("app.email.worker")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not settings.EMAIL_WORKER_ENABLED:
        logger.info("email_worker_disabled worker_id=%s", settings.EMAIL_WORKER_ID)
        return
    verify_connection_and_schema()
    stop = threading.Event()
    for selected_signal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(selected_signal, lambda _signum, _frame: stop.set())
    while not stop.is_set():
        try:
            processed = EmailOutboxService.process_one(worker_id=settings.EMAIL_WORKER_ID)
            stop.wait(0.1 if processed else settings.EMAIL_WORKER_POLL_SECONDS)
        except Exception:
            logger.error("email_worker_cycle_failed worker_id=%s", settings.EMAIL_WORKER_ID)
            stop.wait(settings.EMAIL_WORKER_POLL_SECONDS)
    try:
        with SessionLocal.begin() as db:
            EmailOutboxService.heartbeat(db, settings.EMAIL_WORKER_ID, state="stopping")
    except Exception:
        logger.warning("email_worker_stopping_heartbeat_failed worker_id=%s", settings.EMAIL_WORKER_ID)


if __name__ == "__main__":
    main()
