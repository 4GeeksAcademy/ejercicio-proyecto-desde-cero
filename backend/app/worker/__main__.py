"""Proceso worker: `python -m app.worker`. Ejecuta los trabajos periódicamente (polling a PostgreSQL)."""

import asyncio
import signal
from collections.abc import Awaitable, Callable

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import dispose_engine, get_sessionmaker
from app.core.logging import configure_logging
from app.core.mail import get_mailer
from app.modules.bookings.service import expire_due_bookings
from app.modules.notifications.service import deliver_pending_emails
from app.worker.jobs import process_outbox, send_reminders

log = structlog.get_logger()


async def run_cycle() -> dict[str, int]:
    """Una pasada completa. Cada trabajo usa su propia sesión: si uno falla, los demás siguen."""
    sm = get_sessionmaker()
    results: dict[str, int] = {}
    jobs: dict[str, Callable[[AsyncSession], Awaitable[int]]] = {
        "expired": expire_due_bookings,
        "events": process_outbox,
        "reminders": send_reminders,
    }
    for name, job in jobs.items():
        try:
            async with sm() as session:
                results[name] = await job(session)
        except Exception:
            log.exception("worker_job_failed", job=name)
    try:
        async with sm() as session:
            sent, failed = await deliver_pending_emails(session, get_mailer())
            results["emails_sent"], results["emails_failed"] = sent, failed
    except Exception:
        log.exception("worker_job_failed", job="emails")
    return results


async def main() -> None:
    configure_logging()
    interval = get_settings().worker_poll_seconds
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    log.info("worker_started", event_name="worker_started", interval=interval)
    while not stop.is_set():
        results = await run_cycle()
        if any(results.values()):
            log.info("worker_cycle", event_name="worker_cycle", **results)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            pass
    await dispose_engine()
    log.info("worker_stopped", event_name="worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
