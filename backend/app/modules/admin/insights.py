"""Auditoría consultable y métricas de NEGOCIO para el dashboard (distintas de la telemetría técnica)."""

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.modules.audit.models import AuditLog
from app.modules.bookings.availability import seats_taken
from app.modules.bookings.models import Booking
from app.modules.courses.models import Course
from app.modules.payments.models import Commission, Payment


async def list_audit(
    session: AsyncSession, *, action: str | None, resource_type: str | None, limit: int, offset: int
) -> tuple[list[AuditLog], int]:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(AuditLog.id.desc()).limit(limit).offset(offset))).scalars().all()
    return list(rows), total


async def business_metrics(session: AsyncSession, include_money: bool) -> dict[str, Any]:
    now = clock.now()
    by_status = dict((await session.execute(select(Booking.status, func.count()).group_by(Booking.status))).all())
    courses_by_status = dict((await session.execute(select(Course.status, func.count()).group_by(Course.status))).all())
    upcoming = (
        (
            await session.execute(
                select(Course)
                .where(Course.status == "ACTIVE", Course.starts_at > now)
                .order_by(Course.starts_at)
                .limit(5)
            )
        )
        .scalars()
        .unique()
        .all()
    )
    taken = await seats_taken(session, [c.id for c in upcoming], now)
    upcoming_out = [
        {
            "id": str(c.id),
            "name": c.translations[0].name,
            "starts_at": c.starts_at.isoformat(),
            "capacity": c.capacity,
            "seats_taken": taken[c.id],
            "occupancy_pct": round(100 * taken[c.id] / c.capacity),
        }
        for c in upcoming
    ]
    last_30 = now - timedelta(days=30)
    created_30 = (
        await session.execute(select(func.count()).select_from(Booking).where(Booking.created_at >= last_30))
    ).scalar_one()
    payments_by_status = dict(
        (await session.execute(select(Payment.status, func.count()).group_by(Payment.status))).all()
    )
    out: dict[str, Any] = {
        "bookings_by_status": by_status,
        "pending_approval": by_status.get("PENDING_APPROVAL", 0),
        "pending_payment": by_status.get("PENDING_PAYMENT", 0),
        "bookings_created_last_30_days": created_30,
        "courses_by_status": courses_by_status,
        "upcoming_courses": upcoming_out,
        "payments_by_status": payments_by_status,
    }
    if include_money:
        rows = (
            await session.execute(
                select(Commission.currency, func.sum(Commission.gross_minor), func.sum(Commission.commission_minor))
                .where(Commission.status != "REVERSED")
                .group_by(Commission.currency)
            )
        ).all()
        out["revenue_by_currency"] = {c: {"gross_minor": int(g), "commission_minor": int(m)} for c, g, m in rows}
    return out
