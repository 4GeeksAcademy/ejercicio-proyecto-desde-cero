"""La BD es la última línea de defensa: probamos que las constraints funcionan."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.modules.bookings.models import Booking
from tests.factories import make_course, make_user


async def test_roles_seeded(session):
    n = (await session.execute(text("SELECT count(*) FROM roles"))).scalar_one()
    assert n == 3


async def test_course_capacity_must_be_positive(session):
    with pytest.raises(IntegrityError):
        await make_course(session, capacity=0)
        await session.flush()


async def test_course_price_not_negative(session):
    with pytest.raises(IntegrityError):
        await make_course(session, price_minor=-1)


async def test_email_unique_case_insensitive(session):
    await make_user(session, "Ana@Example.com")
    with pytest.raises(IntegrityError):
        await make_user(session, "ana@example.com")


async def test_one_active_booking_per_user_and_course(session):
    u, c = await make_user(session), await make_course(session)
    session.add(Booking(course_id=c.id, user_id=u.id, status="PENDING_PAYMENT", price_minor=1, currency="COP"))
    await session.flush()
    session.add(Booking(course_id=c.id, user_id=u.id, status="CONFIRMED", price_minor=1, currency="COP"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_can_rebook_after_cancel(session):
    u, c = await make_user(session), await make_course(session)
    session.add(Booking(course_id=c.id, user_id=u.id, status="CANCELLED", price_minor=1, currency="COP"))
    session.add(Booking(course_id=c.id, user_id=u.id, status="PENDING_PAYMENT", price_minor=1, currency="COP"))
    await session.flush()


async def test_invalid_booking_status_rejected(session):
    u, c = await make_user(session), await make_course(session)
    session.add(Booking(course_id=c.id, user_id=u.id, status="HACKED", price_minor=1, currency="COP"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_audit_log_is_append_only(session):
    await session.execute(text("INSERT INTO audit_logs (action, resource_type) VALUES ('x', 'y')"))
    with pytest.raises(DBAPIError):
        await session.execute(text("UPDATE audit_logs SET action = 'z'"))
