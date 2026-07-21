from __future__ import annotations

import asyncio
import logging
import signal

from app.core.config import settings
from app.db.database import SessionLocal
from app.services.raffle_scheduler_service import RaffleSchedulerService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app.raffle_scheduler")


async def run() -> None:
    if not settings.RAFFLE_SCHEDULER_ENABLED:
        logger.info("raffle_scheduler_disabled worker_id=%s", settings.RAFFLE_SCHEDULER_WORKER_ID)
        return
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    service = RaffleSchedulerService()
    logger.info("raffle_scheduler_started worker_id=%s poll_seconds=%s", service.worker_id, settings.RAFFLE_SCHEDULER_POLL_SECONDS)
    while not stop.is_set():
        db = SessionLocal()
        try:
            while await service.poll_once(db):
                pass
        except Exception:
            db.rollback()
            logger.exception("raffle_scheduler_poll_failed worker_id=%s", service.worker_id)
        finally:
            db.close()
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.RAFFLE_SCHEDULER_POLL_SECONDS)
        except TimeoutError:
            pass
    logger.info("raffle_scheduler_stopped worker_id=%s", service.worker_id)


if __name__ == "__main__":
    asyncio.run(run())
