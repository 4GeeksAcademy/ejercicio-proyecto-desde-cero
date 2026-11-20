"""Traduce eventos de dominio (outbox) en notificaciones. Cada handler es IDEMPOTENTE."""

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Permission, Role, RolePermission, User, UserRole
from app.modules.bookings.models import Booking
from app.modules.core_events.models import DomainEvent
from app.modules.courses.models import Course
from app.modules.notifications.service import notify

Handler = Callable[[AsyncSession, DomainEvent], Awaitable[None]]


def _fmt_when(course: Course, locale: str) -> str:
    local = course.starts_at.astimezone(ZoneInfo(course.timezone))
    return local.strftime("%d/%m/%Y %H:%M") if locale == "es" else local.strftime("%Y-%m-%d %H:%M")


async def _context(session: AsyncSession, booking_id: uuid.UUID) -> tuple[Booking, Course, User]:
    booking = await session.get(Booking, booking_id)
    if booking is None:
        raise LookupError("booking not found")
    course = (
        (
            await session.execute(
                select(Course).where(Course.id == booking.course_id).execution_options(populate_existing=True)
            )
        )
        .scalars()
        .unique()
        .one()
    )
    user = await session.get(User, booking.user_id)
    if user is None:
        raise LookupError("user not found")
    return booking, course, user


def _data(booking: Booking, course: Course, user: User) -> dict[str, str]:
    locale = user.profile.preferred_locale
    tr = next((t for t in course.translations if t.locale == locale), None) or course.translations[0]
    return {
        "course": tr.name,
        "when": _fmt_when(course, locale),
        "address": course.venue.address,
        "deadline": _fmt_when_dt(booking.expires_at, course.timezone, locale) if booking.expires_at else "",
        "booking_id": str(booking.id),
        "status": booking.status,
    }


def _fmt_when_dt(dt: datetime, tz: str, locale: str) -> str:
    local = dt.astimezone(ZoneInfo(tz))
    return local.strftime("%d/%m/%Y %H:%M") if locale == "es" else local.strftime("%Y-%m-%d %H:%M")


async def _booking_of(session: AsyncSession, event: DomainEvent) -> tuple[Booking, Course, User]:
    return await _context(session, uuid.UUID(event.payload["booking_id"]))


def _user_kind(kind: str) -> Handler:
    async def handler(session: AsyncSession, event: DomainEvent) -> None:
        booking, course, user = await _booking_of(session, event)
        await notify(session, user, kind, _data(booking, course, user), dedupe_key=f"event:{event.id}")

    return handler


async def staff_with_permission(session: AsyncSession, permission: str) -> list[User]:
    stmt = (
        select(User)
        .distinct()
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(Permission.name == permission, User.is_active.is_(True))
    )
    return list((await session.execute(stmt)).scalars().all())


async def on_payment_completed(session: AsyncSession, event: DomainEvent) -> None:
    booking, course, user = await _booking_of(session, event)
    if event.payload.get("booking_status") != "PENDING_APPROVAL":
        return  # auto-aprobado: ya llegará 'booking_approved'
    data = _data(booking, course, user)
    await notify(session, user, "payment_completed", data, dedupe_key=f"event:{event.id}")
    for staff in await staff_with_permission(session, "booking:approve"):
        await notify(session, staff, "admin_pending_approval", data, dedupe_key=f"event:{event.id}", email=False)


async def on_refund_needed(session: AsyncSession, event: DomainEvent) -> None:
    for staff in await staff_with_permission(session, "payment:refund"):
        await notify(
            session,
            staff,
            "admin_refund_needed",
            {"status": event.payload.get("booking_status", "")},
            dedupe_key=f"event:{event.id}",
            email=False,
        )


HANDLERS: dict[tuple[str, str], Handler] = {
    ("booking", "booking_created"): _user_kind("booking_created"),
    ("booking", "booking_approved"): _user_kind("booking_approved"),
    ("booking", "booking_rejected"): _user_kind("booking_rejected"),
    ("booking", "booking_cancelled"): _user_kind("booking_cancelled"),
    ("booking", "booking_expired"): _user_kind("booking_expired"),
    ("booking", "course_cancelled"): _user_kind("course_cancelled"),
    ("payment", "payment_completed"): on_payment_completed,
    ("payment", "payment_failed"): _user_kind("payment_failed"),
    ("payment", "payment_refunded"): _user_kind("payment_refunded"),
    ("payment", "payment_needs_refund"): on_refund_needed,
}
