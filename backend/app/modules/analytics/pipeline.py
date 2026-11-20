"""Pipeline: EVENTO (outbox) → VALIDACIÓN → TRANSFORMACIÓN → CARGA (idempotente) → MÉTRICAS.

Sin Kafka/Airflow/warehouse: a esta escala basta PostgreSQL con un esquema separado. Si el volumen creciera,
el outbox sigue siendo la fuente de verdad y se podría cargar otro almacén analítico sin tocar el dominio.
"""

import uuid
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

import structlog
from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.models import AnalyticsEvent, DailyCourseMetrics
from app.modules.bookings.models import Booking
from app.modules.core_events.models import DomainEvent

log = structlog.get_logger()
BOGOTA = ZoneInfo("America/Bogota")

# (aggregate_type, event_type) -> columna de métrica que incrementa
METRIC_FOR: dict[tuple[str, str], str] = {
    ("course", "course_viewed"): "course_views",
    ("booking", "booking_created"): "bookings_created",
    ("booking", "booking_approved"): "bookings_confirmed",
    ("booking", "booking_cancelled"): "bookings_cancelled",
    ("booking", "course_cancelled"): "bookings_cancelled",
    ("booking", "booking_expired"): "bookings_expired",
    ("payment", "payment_completed"): "payments_completed",
    ("payment", "payment_failed"): "payments_failed",
}


class ValidEvent(BaseModel):
    """Contrato mínimo que debe cumplir un evento para entrar en analítica. Sin datos personales."""

    event_id: uuid.UUID
    event_type: Literal[
        "course_viewed",
        "booking_created",
        "booking_approved",
        "booking_cancelled",
        "course_cancelled",
        "booking_expired",
        "payment_completed",
        "payment_failed",
    ]
    occurred_at: datetime
    course_id: uuid.UUID | None = None
    booking_id: uuid.UUID | None = None


async def _resolve_course(session: AsyncSession, ev: ValidEvent) -> uuid.UUID | None:
    if ev.course_id:
        return ev.course_id
    if ev.booking_id:  # los eventos de pago traen el booking: enriquecemos con el curso
        return (
            await session.execute(select(Booking.course_id).where(Booking.id == ev.booking_id))
        ).scalar_one_or_none()
    return None


async def consume(session: AsyncSession, event: DomainEvent) -> bool:
    """Procesa UN evento. Devuelve True si cargó algo. Idempotente."""
    column = METRIC_FOR.get((event.aggregate_type, event.event_type))
    if column is None:
        return False  # evento sin valor analítico
    try:
        valid = ValidEvent(
            event_id=event.id,
            event_type=event.event_type,
            occurred_at=event.occurred_at,
            course_id=event.payload.get("course_id"),
            booking_id=event.payload.get("booking_id"),
        )
    except ValidationError:
        log.warning("analytics_event_invalid", event_name="analytics_event_invalid", event_id=str(event.id))
        return False
    course_id = await _resolve_course(session, valid)
    if course_id is None:
        return False
    day = valid.occurred_at.astimezone(BOGOTA).date()
    inserted = (
        await session.execute(
            pg_insert(AnalyticsEvent)
            .values(
                event_id=valid.event_id,
                event_type=valid.event_type,
                occurred_at=valid.occurred_at,
                day=day,
                course_id=course_id,
            )
            .on_conflict_do_nothing(index_elements=["event_id"])
            .returning(AnalyticsEvent.event_id)
        )
    ).scalar_one_or_none()
    if inserted is None:
        return False  # ya contabilizado: reprocesar no duplica
    col = getattr(DailyCourseMetrics, column)
    await session.execute(
        pg_insert(DailyCourseMetrics)
        .values(day=day, course_id=course_id, **{column: 1})
        .on_conflict_do_update(index_elements=["day", "course_id"], set_={column: col + 1})
    )
    return True


async def rebuild(session: AsyncSession) -> int:
    """Reconstruye TODA la analítica desde el outbox (reproducibilidad / correcciones / backfill)."""
    await session.execute(delete(DailyCourseMetrics))
    await session.execute(delete(AnalyticsEvent))
    n = 0
    for ev in (await session.execute(select(DomainEvent).order_by(DomainEvent.occurred_at))).scalars():
        n += await consume(session, ev)
    await session.commit()
    return n


async def dashboard(session: AsyncSession, days: int) -> dict[str, object]:
    rows = (
        (
            await session.execute(
                text(
                    """
                SELECT m.day, SUM(course_views) views, SUM(bookings_created) created, SUM(bookings_confirmed) confirmed,
                       SUM(bookings_cancelled) cancelled, SUM(bookings_expired) expired,
                       SUM(payments_completed) paid, SUM(payments_failed) failed
                FROM analytics.daily_course_metrics m
                WHERE m.day >= (now() AT TIME ZONE 'America/Bogota')::date - :d
                GROUP BY m.day ORDER BY m.day
                """
                ),
                {"d": days},
            )
        )
        .mappings()
        .all()
    )
    per_course = (
        (
            await session.execute(
                text(
                    """
                SELECT m.course_id::text AS course_id,
                       (SELECT t.name FROM course_translations t WHERE t.course_id = m.course_id ORDER BY (t.locale = 'es') DESC LIMIT 1) AS name,
                       SUM(course_views) views, SUM(bookings_created) created, SUM(bookings_confirmed) confirmed,
                       SUM(bookings_cancelled) cancelled, SUM(bookings_expired) expired
                FROM analytics.daily_course_metrics m
                WHERE m.day >= (now() AT TIME ZONE 'America/Bogota')::date - :d
                GROUP BY m.course_id ORDER BY created DESC
                """
                ),
                {"d": days},
            )
        )
        .mappings()
        .all()
    )
    series = [{k: (v.isoformat() if k == "day" else int(v)) for k, v in r.items()} for r in rows]
    courses = []
    for r in per_course:
        d = {k: (v if k in ("course_id", "name") else int(v)) for k, v in r.items()}
        d["view_to_booking_pct"] = round(100 * d["created"] / d["views"]) if d["views"] else None
        d["confirmation_pct"] = round(100 * d["confirmed"] / d["created"]) if d["created"] else None
        courses.append(d)
    return {"days": days, "series": series, "by_course": courses}
