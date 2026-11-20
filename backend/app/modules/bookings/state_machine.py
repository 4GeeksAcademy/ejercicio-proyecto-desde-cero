"""Máquina de estados de las reservas: lógica PURA (sin base de datos), fácil de probar.

Una reserva solo cambia de estado mediante un EVENTO permitido, ejecutado por un ACTOR autorizado.
Cualquier otra combinación está PROHIBIDA y lanza InvalidTransitionError.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.core.errors import ConflictError
from app.modules.bookings.models import BookingStatus as S


class Event(StrEnum):
    CREATED = "booking_created"
    PAYMENT_INITIATED = "payment_initiated"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_CONFIRMED = "payment_confirmed"
    AWAIT_APPROVAL = "awaiting_approval"
    APPROVED = "booking_approved"
    REJECTED = "booking_rejected"
    EXPIRED = "booking_expired"
    CANCELLED = "booking_cancelled"
    COURSE_CANCELLED = "course_cancelled"
    REFUND_COMPLETED = "refund_completed"


class Actor(StrEnum):
    USER = "USER"  # el dueño de la reserva
    ADMIN = "ADMIN"  # admin / propietario
    SYSTEM = "SYSTEM"  # worker, webhooks verificados, reglas automáticas


@dataclass(frozen=True)
class Rule:
    sources: frozenset[S | None]
    target: S
    actors: frozenset[Actor]


def _r(sources: set[S | None], target: S, *actors: Actor) -> Rule:
    return Rule(frozenset(sources), target, frozenset(actors))


TRANSITIONS: dict[Event, Rule] = {
    Event.CREATED: _r({None}, S.PENDING_PAYMENT, Actor.USER),
    Event.PAYMENT_INITIATED: _r({S.PENDING_PAYMENT}, S.PAYMENT_PROCESSING, Actor.SYSTEM),
    Event.PAYMENT_FAILED: _r({S.PAYMENT_PROCESSING}, S.PENDING_PAYMENT, Actor.SYSTEM),
    # Solo el SISTEMA confirma pagos (webhook verificado): ni el cliente ni el admin pueden saltarse esto.
    Event.PAYMENT_CONFIRMED: _r({S.PENDING_PAYMENT, S.PAYMENT_PROCESSING}, S.PAID, Actor.SYSTEM),
    Event.AWAIT_APPROVAL: _r({S.PAID}, S.PENDING_APPROVAL, Actor.SYSTEM),
    Event.APPROVED: _r({S.PENDING_APPROVAL}, S.CONFIRMED, Actor.ADMIN, Actor.SYSTEM),  # SYSTEM: auto-aprobación
    Event.REJECTED: _r({S.PENDING_APPROVAL}, S.REJECTED, Actor.ADMIN),
    Event.EXPIRED: _r({S.PENDING_PAYMENT}, S.EXPIRED, Actor.SYSTEM),
    Event.CANCELLED: _r(
        {S.PENDING_PAYMENT, S.PENDING_APPROVAL, S.CONFIRMED, S.PAID}, S.CANCELLED, Actor.USER, Actor.ADMIN
    ),
    Event.COURSE_CANCELLED: _r(
        {S.PENDING_PAYMENT, S.PAYMENT_PROCESSING, S.PAID, S.PENDING_APPROVAL, S.CONFIRMED}, S.CANCELLED, Actor.ADMIN
    ),
    Event.REFUND_COMPLETED: _r({S.CANCELLED, S.REJECTED}, S.REFUNDED, Actor.SYSTEM),
}

# Qué estados necesitan devolver dinero si se cancela/rechaza (ya hay pago).
PAID_STATES = frozenset({S.PAID, S.PENDING_APPROVAL, S.CONFIRMED})


class InvalidTransitionError(ConflictError):
    code = "INVALID_STATE_TRANSITION"
    message = "Esa operación no está permitida en el estado actual de la reserva."


class ActorNotAllowedError(ConflictError):
    code = "ACTOR_NOT_ALLOWED"
    message = "No tienes permiso para realizar esa transición."


def next_status(current: S | None, event: Event, actor: Actor) -> S:
    rule = TRANSITIONS[event]
    if current not in rule.sources:
        raise InvalidTransitionError(details={"from": current.value if current else None, "event": event.value})
    if actor not in rule.actors:
        raise ActorNotAllowedError(details={"event": event.value, "actor": actor.value})
    return rule.target
