"""Trabajos en segundo plano. Cada uno es idempotente y seguro con varios workers (SKIP LOCKED)."""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.modules.bookings.models import Booking
from app.modules.core_events.models import DomainEvent
from app.modules.courses.models import Course
from app.modules.notifications.handlers import HANDLERS, _context, _data
from app.modules.notifications.service import notify

log = structlog.get_logger()
MAX_EVENT_ATTEMPTS = 5


async def process_outbox(session: AsyncSession, batch_size: int = 100) -> int:
    """Consume eventos de dominio. Un evento "venenoso" no bloquea a los demás: se reintenta y, tras 5 fallos, queda aparcado."""
    events = (
        (
            await session.execute(
                select(DomainEvent)
                .where(DomainEvent.processed_at.is_(None), DomainEvent.attempts < MAX_EVENT_ATTEMPTS)
                .order_by(DomainEvent.occurred_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    done = 0
    for ev in events:
        handler = HANDLERS.get((ev.aggregate_type, ev.event_type))
        try:
            async with session.begin_nested():  # SAVEPOINT: si el handler falla, solo se deshace ESE evento
                if handler:
                    await handler(session, ev)
                ev.processed_at = clock.now()
            done += 1
        except Exception as exc:
            ev.attempts += 1
            ev.last_error = type(exc).__name__
            log.error(
                "outbox_event_failed",
                event_name="outbox_event_failed",
                event_id=str(ev.id),
                type=ev.event_type,
                attempts=ev.attempts,
            )
    await session.commit()
    return done


async def send_reminders(session: AsyncSession, hours: int = 24) -> int:
    """Un recordatorio por reserva confirmada cuando faltan <= `hours` horas (dedupe_key evita repetirlo)."""
    from datetime import timedelta

    now = clock.now()
    rows = (
        (
            await session.execute(
                select(Booking.id)
                .join(Course, Course.id == Booking.course_id)
                .where(
                    Booking.status == "CONFIRMED",
                    Course.starts_at > now,
                    Course.starts_at <= now + timedelta(hours=hours),
                )
            )
        )
        .scalars()
        .all()
    )
    for booking_id in rows:
        booking, course, user = await _context(session, booking_id)
        await notify(
            session, user, "booking_reminder", _data(booking, course, user), dedupe_key=f"reminder:{booking_id}"
        )
    await session.commit()
    return len(rows)
