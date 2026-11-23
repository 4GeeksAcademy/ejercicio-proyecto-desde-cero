import itertools

import pytest

from app.modules.bookings.models import SEAT_HOLDING_STATUSES
from app.modules.bookings.models import BookingStatus as S
from app.modules.bookings.state_machine import (
    TRANSITIONS,
    Actor,
    ActorNotAllowedError,
    Event,
    InvalidTransitionError,
    next_status,
)


def test_happy_path():
    s = next_status(None, Event.CREATED, Actor.USER)
    assert s == S.PENDING_PAYMENT
    s = next_status(s, Event.PAYMENT_INITIATED, Actor.SYSTEM)
    s = next_status(s, Event.PAYMENT_CONFIRMED, Actor.SYSTEM)
    assert s == S.PAID
    s = next_status(s, Event.AWAIT_APPROVAL, Actor.SYSTEM)
    assert s == S.PENDING_APPROVAL
    assert next_status(s, Event.APPROVED, Actor.ADMIN) == S.CONFIRMED


def test_cannot_skip_payment():
    with pytest.raises(InvalidTransitionError):
        next_status(S.PENDING_PAYMENT, Event.APPROVED, Actor.ADMIN)


@pytest.mark.parametrize("event", [Event.PAYMENT_CONFIRMED, Event.APPROVED, Event.REJECTED, Event.EXPIRED])
def test_client_cannot_perform_privileged_events(event):
    for src in TRANSITIONS[event].sources:
        with pytest.raises(ActorNotAllowedError):
            next_status(src, event, Actor.USER)


def test_admin_cannot_confirm_payments():
    with pytest.raises(ActorNotAllowedError):
        next_status(S.PENDING_PAYMENT, Event.PAYMENT_CONFIRMED, Actor.ADMIN)


@pytest.mark.parametrize("terminal", [S.EXPIRED, S.REFUNDED])
def test_terminal_states_have_no_exit(terminal):
    for event, actor in itertools.product(Event, Actor):
        with pytest.raises((InvalidTransitionError, ActorNotAllowedError)):
            next_status(terminal, event, actor)


def test_confirmed_cannot_go_back():
    for event in (Event.PAYMENT_INITIATED, Event.PAYMENT_FAILED, Event.AWAIT_APPROVAL, Event.EXPIRED, Event.APPROVED):
        with pytest.raises(InvalidTransitionError):
            next_status(S.CONFIRMED, event, Actor.SYSTEM)


def test_expire_only_while_payment_is_pending_or_abandoned():
    """Caduca desde "pendiente de pago" y desde "procesando pago" (pago abandonado, RN-15); nunca una reserva ya pagada."""
    expirable = {S.PENDING_PAYMENT, S.PAYMENT_PROCESSING}
    for src in expirable:
        assert next_status(src, Event.EXPIRED, Actor.SYSTEM) == S.EXPIRED
    for src in set(S) - expirable:
        with pytest.raises(InvalidTransitionError):
            next_status(src, Event.EXPIRED, Actor.SYSTEM)
    for actor in (Actor.USER, Actor.ADMIN):  # solo el sistema puede caducar
        with pytest.raises(ActorNotAllowedError):
            next_status(S.PAYMENT_PROCESSING, Event.EXPIRED, actor)


def test_no_transition_leaves_a_dead_end_without_reason():
    """Todo estado no terminal tiene al menos una salida; los que liberan plaza no están en SEAT_HOLDING."""
    sources = {s for r in TRANSITIONS.values() for s in r.sources if s}
    non_terminal = set(S) - {S.EXPIRED, S.REFUNDED}
    assert non_terminal <= sources
    for s in (S.REJECTED, S.CANCELLED, S.EXPIRED, S.REFUNDED):
        assert s not in SEAT_HOLDING_STATUSES


def test_every_rule_targets_valid_status_and_has_actor():
    for rule in TRANSITIONS.values():
        assert rule.target in set(S) and rule.actors
