"""Cálculo FIABLE de plazas ocupadas. Única fuente de verdad (la usan catálogo, reservas y admin).

Una plaza está ocupada si la reserva está en un estado que "ocupa plaza", EXCEPTO una PENDING_PAYMENT cuyo
plazo de pago ya venció (aunque el job de caducidad aún no la haya marcado EXPIRED). Así la corrección
NO depende de que el worker esté funcionando.
"""

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, and_, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bookings.models import SEAT_HOLDING_STATUSES, Booking, BookingStatus
from app.modules.courses.models import Course

_HOLDING = [s.value for s in SEAT_HOLDING_STATUSES]


def holding_condition(now: datetime) -> ColumnElement[bool]:
    stale_hold = and_(Booking.status == BookingStatus.PENDING_PAYMENT.value, Booking.expires_at <= now)
    return and_(Booking.status.in_(_HOLDING), not_(stale_hold))


def taken_subquery(now: datetime) -> ColumnElement[int]:
    """Subconsulta correlacionada con `courses.id` (para filtrar/ordenar dentro de una consulta de cursos)."""
    return (
        select(func.count(Booking.id)).where(Booking.course_id == Course.id, holding_condition(now)).scalar_subquery()
    )


async def seats_taken(session: AsyncSession, course_ids: list[uuid.UUID], now: datetime) -> dict[uuid.UUID, int]:
    if not course_ids:
        return {}
    stmt = (
        select(Booking.course_id, func.count(Booking.id))
        .where(Booking.course_id.in_(course_ids), holding_condition(now))
        .group_by(Booking.course_id)
    )
    rows = (await session.execute(stmt)).all()
    counts = {cid: 0 for cid in course_ids}
    for cid, n in rows:
        counts[cid] = n
    return counts
