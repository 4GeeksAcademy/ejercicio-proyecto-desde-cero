"""Motor de reservas. TODA la lógica crítica vive aquí (backend), nunca en el frontend.

Garantía anti-sobreventa (ver ADR-0004):
  1. Dentro de UNA transacción bloqueamos la fila del curso (SELECT ... FOR UPDATE).
  2. Contamos plazas ocupadas y, si queda hueco, insertamos.
  3. Un índice único parcial en la BD impide 2 reservas vivas de la misma persona (red de seguridad).
  4. Idempotency-Key: reintentar la misma petición devuelve la misma respuesta, no crea otra reserva.
"""

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

from app.core import clock
from app.core.config import get_settings
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.telemetry import counters, tracer
from app.modules.audit import service as audit
from app.modules.auth.dependencies import Principal
from app.modules.bookings.availability import holding_condition, seats_taken
from app.modules.bookings.models import Booking, BookingStatus, BookingStatusHistory, IdempotencyKey
from app.modules.bookings.schemas import AdminBookingOut, BookingCourse, BookingOut, HistoryItem
from app.modules.bookings.state_machine import PAID_STATES, Actor, Event, next_status
from app.modules.core_events import service as events
from app.modules.courses.models import Course, CourseStatus

log = structlog.get_logger()
S = BookingStatus


class CourseFullError(ConflictError):
    code = "COURSE_FULL"
    message = "Este curso ya no tiene plazas disponibles."


class AlreadyBookedError(ConflictError):
    code = "ALREADY_BOOKED"
    message = "Ya tienes una reserva activa para este curso."


# ------------------------------------------------------------------ núcleo de transiciones


async def apply_transition(
    session: AsyncSession,
    booking: Booking,
    event: Event,
    actor: Actor,
    actor_id: uuid.UUID | None = None,
    reason: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """ÚNICO lugar donde cambia `booking.status`. Valida, guarda historial y emite evento (outbox)."""
    previous = S(booking.status) if booking.status else None
    target = next_status(previous, event, actor)
    booking.status = target.value
    session.add(
        BookingStatusHistory(
            booking_id=booking.id,
            from_status=previous.value if previous else None,
            to_status=target.value,
            event=event.value,
            actor_type=actor.value,
            actor_user_id=actor_id,
            reason=reason,
        )
    )
    payload: dict[str, Any] = {
        "booking_id": str(booking.id),
        "course_id": str(booking.course_id),
        "from": previous.value if previous else None,
        "to": target.value,
    }
    if previous in PAID_STATES and target in (S.CANCELLED, S.REJECTED):
        payload["refund_required"] = True  # [PENDIENTE P-04/P-05] la política exacta se decide en el Hito 6
    if extra:
        payload.update(extra)
    events.emit(session, event.value, "booking", booking.id, payload)
    counters.add("tallerya.booking.transitions", event=event.value, to_status=target.value)
    log.info("booking_transition", event_name=event.value, booking_id=str(booking.id), status=target.value)


# ------------------------------------------------------------------ presentación


def _can_cancel(booking: Booking, course: Course, now: datetime) -> bool:
    cutoff = timedelta(hours=get_settings().booking_cutoff_hours)
    return booking.status in (S.PENDING_PAYMENT, S.PENDING_APPROVAL, S.CONFIRMED) and course.starts_at - now > cutoff


_NEXT_ACTION = {
    S.PENDING_PAYMENT: "pay",
    S.PAYMENT_PROCESSING: "wait_payment",
    S.PAID: "wait_approval",
    S.PENDING_APPROVAL: "wait_approval",
    S.CONFIRMED: "attend",
}


def to_out(
    booking: Booking, course: Course, locale: str, history: list[BookingStatusHistory] | None = None
) -> BookingOut:
    tr = next((t for t in course.translations if t.locale == locale), None) or course.translations[0]
    return BookingOut(
        id=booking.id,
        status=booking.status,
        expires_at=booking.expires_at,
        price_minor=booking.price_minor,
        currency=booking.currency,
        created_at=booking.created_at,
        course=BookingCourse(
            id=course.id,
            slug=tr.slug,
            name=tr.name,
            starts_at=course.starts_at,
            ends_at=course.ends_at,
            timezone=course.timezone,
            address=course.venue.address,
        ),
        next_action=_NEXT_ACTION.get(S(booking.status), "none"),
        can_cancel=_can_cancel(booking, course, clock.now()),
        history=None
        if history is None
        else [
            HistoryItem(from_status=h.from_status, to_status=h.to_status, event=h.event, at=h.created_at)
            for h in history
        ],
    )


# ------------------------------------------------------------------ crear reserva (CRÍTICO)


async def _lock_course(session: AsyncSession, course_id: uuid.UUID) -> Course:
    course = (
        (
            await session.execute(
                select(Course)
                .where(Course.id == course_id)
                .options(lazyload(Course.category), lazyload(Course.venue))
                .with_for_update(of=Course)
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .unique()
        .one_or_none()
    )
    if course is None:
        raise NotFoundError("Curso no encontrado.", code="COURSE_NOT_FOUND")
    return course


def _validate_course_bookable(course: Course, now: datetime) -> None:
    if course.status == CourseStatus.CANCELLED.value:
        raise BusinessRuleError("Este curso ha sido cancelado.", code="COURSE_CANCELLED")
    if course.status != CourseStatus.ACTIVE.value:
        raise BusinessRuleError("Este curso no está disponible para reservas.", code="COURSE_NOT_AVAILABLE")
    if course.ends_at <= now:
        raise BusinessRuleError("Este curso ya ha finalizado.", code="COURSE_FINISHED")
    if course.starts_at - now <= timedelta(hours=get_settings().booking_cutoff_hours):
        raise BusinessRuleError(
            "Ya no se admiten reservas: faltan menos de 24 horas para el inicio.", code="BOOKING_WINDOW_CLOSED"
        )


async def create_booking(
    session: AsyncSession, principal: Principal, course_id: uuid.UUID, idempotency_key: str | None, locale: str = "es"
) -> tuple[BookingOut, bool]:
    """Devuelve (reserva, creada_ahora). `creada_ahora=False` => respuesta repetida por Idempotency-Key."""
    with tracer().start_as_current_span("booking.create") as span:
        span.set_attribute("course.id", str(course_id))
        return await _create_booking(session, principal, course_id, idempotency_key, locale)


async def _create_booking(
    session: AsyncSession, principal: Principal, course_id: uuid.UUID, idempotency_key: str | None, locale: str
) -> tuple[BookingOut, bool]:
    user_id = principal.user.id
    request_hash = hashlib.sha256(f"booking.create:{course_id}".encode()).hexdigest()

    if idempotency_key:
        stored = await session.get(IdempotencyKey, (user_id, "booking.create", idempotency_key))
        if stored:
            if stored.request_hash != request_hash:
                raise BusinessRuleError(
                    "Esa Idempotency-Key ya se usó con otra petición.", code="IDEMPOTENCY_KEY_REUSED"
                )
            return BookingOut.model_validate(stored.response_body), False

    now = clock.now()
    course = await _lock_course(session, course_id)  # <-- la "llave de la sala": serializa reservas del curso
    _validate_course_bookable(course, now)

    # Caducar (perezosamente) un hold vencido de esta persona para poder reservar de nuevo.
    stale = (
        (
            await session.execute(
                select(Booking)
                .where(
                    Booking.course_id == course_id,
                    Booking.user_id == user_id,
                    Booking.status == S.PENDING_PAYMENT.value,
                    Booking.expires_at <= now,
                )
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    for b in stale:
        await apply_transition(session, b, Event.EXPIRED, Actor.SYSTEM)

    already = (
        await session.execute(
            select(Booking.id).where(Booking.course_id == course_id, Booking.user_id == user_id, holding_condition(now))
        )
    ).first()
    if already:
        raise AlreadyBookedError()

    taken = (await seats_taken(session, [course_id], now))[course_id]
    if taken >= course.capacity:
        raise CourseFullError()

    booking = Booking(
        id=uuid.uuid4(),
        course_id=course.id,
        user_id=user_id,
        price_minor=course.price_minor,
        currency=course.currency,
        expires_at=now + timedelta(hours=get_settings().booking_payment_window_hours),
    )
    await apply_transition(session, booking, Event.CREATED, Actor.USER, user_id)  # fija status=PENDING_PAYMENT
    session.add(booking)
    try:
        await session.flush()
    except IntegrityError as exc:  # red de seguridad del índice único parcial
        await session.rollback()
        raise AlreadyBookedError() from exc

    out = to_out(booking, await course_for_view(session, course.id), locale)
    if idempotency_key:
        session.add(
            IdempotencyKey(
                user_id=user_id,
                scope="booking.create",
                key=idempotency_key,
                request_hash=request_hash,
                response_status=201,
                response_body=out.model_dump(mode="json"),
            )
        )
    await session.commit()
    return out, True


async def course_for_view(session: AsyncSession, course_id: uuid.UUID) -> Course:
    return (
        (await session.execute(select(Course).where(Course.id == course_id).execution_options(populate_existing=True)))
        .scalars()
        .unique()
        .one()
    )


# ------------------------------------------------------------------ consultas


async def list_my_bookings(
    session: AsyncSession, user_id: uuid.UUID, status: str | None, limit: int, offset: int, locale: str
) -> tuple[list[BookingOut], int]:
    stmt = select(Booking).where(Booking.user_id == user_id)
    if status:
        stmt = stmt.where(Booking.status == status)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(Booking.created_at.desc()).limit(limit).offset(offset))).scalars().all()
    out = [to_out(b, await course_for_view(session, b.course_id), locale) for b in rows]
    return out, total


async def get_my_booking(session: AsyncSession, user_id: uuid.UUID, booking_id: uuid.UUID, locale: str) -> BookingOut:
    booking = await session.get(Booking, booking_id)
    if booking is None or booking.user_id != user_id:
        raise NotFoundError("Reserva no encontrada.", code="BOOKING_NOT_FOUND")  # 404 también si es ajena
    history = (
        (
            await session.execute(
                select(BookingStatusHistory)
                .where(BookingStatusHistory.booking_id == booking_id)
                .order_by(BookingStatusHistory.seq)
            )
        )
        .scalars()
        .all()
    )
    return to_out(booking, await course_for_view(session, booking.course_id), locale, list(history))


async def lock_booking(session: AsyncSession, booking_id: uuid.UUID) -> Booking:
    b = (await session.execute(select(Booking).where(Booking.id == booking_id).with_for_update())).scalar_one_or_none()
    if b is None:
        raise NotFoundError("Reserva no encontrada.", code="BOOKING_NOT_FOUND")
    return b


# ------------------------------------------------------------------ cancelar / aprobar / rechazar


async def cancel_my_booking(
    session: AsyncSession, principal: Principal, booking_id: uuid.UUID, reason: str | None, locale: str = "es"
) -> BookingOut:
    booking = await lock_booking(session, booking_id)
    if booking.user_id != principal.user.id:
        raise NotFoundError("Reserva no encontrada.", code="BOOKING_NOT_FOUND")
    course = await course_for_view(session, booking.course_id)
    if course.starts_at - clock.now() <= timedelta(hours=get_settings().booking_cutoff_hours):
        raise BusinessRuleError(
            "Ya no puedes cancelar: faltan menos de 24 horas para el inicio.", code="CANCELLATION_WINDOW_CLOSED"
        )
    await apply_transition(session, booking, Event.CANCELLED, Actor.USER, principal.user.id, reason)
    await session.commit()
    return to_out(booking, course, locale)


async def admin_decide(
    session: AsyncSession, principal: Principal, booking_id: uuid.UUID, decision: Event, reason: str | None
) -> AdminBookingOut:
    """Aprobar / rechazar / cancelar (admin). Siempre queda en auditoría."""
    booking = await lock_booking(session, booking_id)
    course = await course_for_view(session, booking.course_id)
    if decision == Event.APPROVED and course.status == CourseStatus.CANCELLED.value:
        raise BusinessRuleError("El curso está cancelado.", code="COURSE_CANCELLED")
    await apply_transition(session, booking, decision, Actor.ADMIN, principal.user.id, reason)
    await audit.record(
        session,
        actor_id=principal.user.id,
        action=f"booking.{decision.value.removeprefix('booking_')}",
        resource_type="booking",
        resource_id=booking.id,
        changes={"to": booking.status, "reason": bool(reason)},
    )
    await session.commit()
    return await admin_view(session, booking, "es")


async def admin_view(session: AsyncSession, booking: Booking, locale: str) -> AdminBookingOut:
    from app.modules.auth.models import User

    user = await session.get(User, booking.user_id)
    assert user is not None  # noqa: S101 (FK garantiza existencia)
    base = to_out(booking, await course_for_view(session, booking.course_id), locale)
    return AdminBookingOut(
        **base.model_dump(), user_id=user.id, user_name=user.profile.full_name, user_email=user.email
    )


async def admin_list(
    session: AsyncSession, *, course_id: uuid.UUID | None, status: str | None, limit: int, offset: int
) -> tuple[list[AdminBookingOut], int]:
    stmt = select(Booking)
    if course_id:
        stmt = stmt.where(Booking.course_id == course_id)
    if status:
        stmt = stmt.where(Booking.status == status)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(Booking.created_at.desc()).limit(limit).offset(offset))).scalars().all()
    return [await admin_view(session, b, "es") for b in rows], total


# ------------------------------------------------------------------ caducidad (job) y curso cancelado


async def expire_due_bookings(session: AsyncSession, batch_size: int = 100) -> int:
    """Marca como EXPIRED las reservas con plazo de pago vencido. Idempotente y seguro con varios workers (SKIP LOCKED)."""
    now = clock.now()
    due = (
        (
            await session.execute(
                select(Booking)
                .where(Booking.status == S.PENDING_PAYMENT.value, Booking.expires_at <= now)
                .order_by(Booking.expires_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    for b in due:
        await apply_transition(session, b, Event.EXPIRED, Actor.SYSTEM)
    await session.commit()
    if due:
        log.info("bookings_expired", event_name="bookings_expired", count=len(due))
    return len(due)


async def cancel_course(session: AsyncSession, course_id: uuid.UUID, principal: Principal, reason: str) -> int:
    """Cancela el curso y TODAS sus reservas vivas (RN-17). Devuelve cuántas reservas se cancelaron."""
    course = await _lock_course(session, course_id)  # bloquea nuevas reservas mientras cancelamos
    if course.status == CourseStatus.CANCELLED.value:
        raise ConflictError("El curso ya está cancelado.", code="COURSE_CANCELLED")
    course.status = CourseStatus.CANCELLED.value
    live = (
        (
            await session.execute(
                select(Booking)
                .where(
                    Booking.course_id == course_id,
                    Booking.status.in_([s.value for s in PAID_STATES | {S.PENDING_PAYMENT, S.PAYMENT_PROCESSING}]),
                )
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    for b in live:
        await apply_transition(session, b, Event.COURSE_CANCELLED, Actor.ADMIN, principal.user.id, reason)
    await audit.record(
        session,
        actor_id=principal.user.id,
        action="course.cancelled",
        resource_type="course",
        resource_id=course_id,
        changes={"bookings_cancelled": len(live)},
    )
    events.emit(session, "course_cancelled", "course", course_id, {"course_id": str(course_id), "bookings": len(live)})
    await session.commit()
    return len(live)


# ------------------------------------------------------------------ puntos de entrada para Pagos (Hito 6)


async def on_payment_initiated(session: AsyncSession, booking_id: uuid.UUID) -> None:
    b = await lock_booking(session, booking_id)
    await apply_transition(session, b, Event.PAYMENT_INITIATED, Actor.SYSTEM)


async def on_payment_failed(session: AsyncSession, booking_id: uuid.UUID) -> None:
    b = await lock_booking(session, booking_id)
    await apply_transition(session, b, Event.PAYMENT_FAILED, Actor.SYSTEM)


async def on_payment_confirmed(session: AsyncSession, booking_id: uuid.UUID) -> BookingStatus:
    """PAID y, en la misma transacción, PENDING_APPROVAL (o CONFIRMED si el curso se auto-aprueba)."""
    b = await lock_booking(session, booking_id)
    await apply_transition(session, b, Event.PAYMENT_CONFIRMED, Actor.SYSTEM)
    await apply_transition(session, b, Event.AWAIT_APPROVAL, Actor.SYSTEM)
    course = await course_for_view(session, b.course_id)
    if not course.requires_approval:
        await apply_transition(session, b, Event.APPROVED, Actor.SYSTEM, reason="auto_approval")
    return S(b.status)


# ------------------------------------------------------------------ QR y check-in [PENDIENTE P-08]


async def qr_for_booking(session: AsyncSession, user_id: uuid.UUID, booking_id: uuid.UUID) -> str:
    from app.modules.bookings import qr

    booking = await session.get(Booking, booking_id)
    if booking is None or booking.user_id != user_id:
        raise NotFoundError("Reserva no encontrada.", code="BOOKING_NOT_FOUND")
    if booking.status != S.CONFIRMED.value:
        raise ConflictError("El QR solo está disponible con la plaza confirmada.", code="QR_NOT_AVAILABLE")
    return qr.make_token(booking.id)


async def check_in(session: AsyncSession, principal: Principal, token: str) -> tuple[AdminBookingOut, bool]:
    """Marca la asistencia al escanear el QR. Idempotente: devuelve (reserva, primera_vez)."""
    from app.modules.bookings import qr

    booking = await lock_booking(session, qr.parse_token(token))
    course = await course_for_view(session, booking.course_id)
    if booking.status != S.CONFIRMED.value or course.status == CourseStatus.CANCELLED.value:
        raise ConflictError("La reserva no está confirmada.", code="CHECKIN_NOT_ALLOWED")
    now = clock.now()
    if not (course.starts_at - timedelta(hours=6) <= now <= course.ends_at + timedelta(hours=6)):
        raise BusinessRuleError("Fuera de la ventana de acceso del curso.", code="CHECKIN_OUT_OF_WINDOW")
    first = booking.checked_in_at is None
    if first:
        booking.checked_in_at = now
        await audit.record(
            session,
            actor_id=principal.user.id,
            action="booking.checked_in",
            resource_type="booking",
            resource_id=booking.id,
        )
        await session.commit()
    return await admin_view(session, booking, "es"), first
