import asyncio
import uuid
from datetime import timedelta

from sqlalchemy import func, select, text

from app.core import clock
from app.modules.bookings import service as booking_service
from app.modules.bookings.models import Booking, BookingStatusHistory
from app.modules.core_events.models import DomainEvent
from tests.factories import make_course, make_user

API = "/api/v1"


async def book(client, course_id, key=None):
    headers = {"Idempotency-Key": key} if key else {}
    return await client.post(f"{API}/bookings", json={"course_id": str(course_id)}, headers=headers)


async def setup(session, auth_client, capacity=5, **kw):
    course = await make_course(session, capacity=capacity, **kw)
    user = await make_user(session, role="CLIENT")
    await session.commit()
    return course, user, await auth_client(user)


async def test_create_booking_happy_path(session, auth_client):
    course, _, c = await setup(session, auth_client)
    r = await book(c, course.id)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == "PENDING_PAYMENT" and b["next_action"] == "pay" and b["can_cancel"] is True
    assert b["price_minor"] == course.price_minor and b["course"]["slug"] == course.translations[0].slug
    hours = (
        clock.now() + timedelta(hours=24) - __import__("datetime").datetime.fromisoformat(b["expires_at"])
    ).total_seconds()
    assert abs(hours) < 60  # plazo de pago ~24 h
    a = (await c.get(f"{API}/courses/{course.id}/availability")).json()
    assert a["seats_taken"] == 1 and a["seats_available"] == 4


async def test_booking_requires_authentication(session, client):
    course = await make_course(session)
    await session.commit()
    r = await book(client, course.id)
    assert r.status_code == 401
    assert (await session.execute(select(func.count()).select_from(Booking))).scalar_one() == 0


async def test_full_course_rejected(session, auth_client):
    course, _, c = await setup(session, auth_client, capacity=1)
    other = await make_user(session, role="CLIENT")
    await session.commit()
    assert (await book(await auth_client(other), course.id)).status_code == 201
    r = await book(c, course.id)
    assert r.status_code == 409 and r.json()["error"]["code"] == "COURSE_FULL"


async def test_unavailable_courses_rejected(session, auth_client):
    user = await make_user(session, role="CLIENT")
    cases = {
        "CANCELLED": "COURSE_CANCELLED",
        "INACTIVE": "COURSE_NOT_AVAILABLE",
        "DRAFT": "COURSE_NOT_AVAILABLE",
    }
    ids = {code_status: (await make_course(session, status=code_status)).id for code_status in cases}
    finished = await make_course(session, hours_ahead=-48)  # ya empezó y terminó
    await session.commit()
    c = await auth_client(user)
    for status, expected in cases.items():
        r = await book(c, ids[status])
        assert r.status_code == 422 and r.json()["error"]["code"] == expected, (status, r.text)
    r = await book(c, finished.id)
    assert r.json()["error"]["code"] == "COURSE_FINISHED"
    r = await book(c, uuid.uuid4())
    assert r.status_code == 404


async def test_booking_window_24h(session, auth_client):
    closed = await make_course(session, hours_ahead=23.9)
    boundary = await make_course(session, hours_ahead=24)  # exactamente 24 h: ya NO (hace falta > 24 h)
    open_ = await make_course(session, hours_ahead=24.1)
    user = await make_user(session, role="CLIENT")
    await session.commit()
    c = await auth_client(user)
    assert (await book(c, closed.id)).json()["error"]["code"] == "BOOKING_WINDOW_CLOSED"
    assert (await book(c, boundary.id)).json()["error"]["code"] == "BOOKING_WINDOW_CLOSED"
    assert (await book(c, open_.id)).status_code == 201


async def test_duplicate_booking_rejected_and_rebook_after_cancel(session, auth_client):
    course, _, c = await setup(session, auth_client)
    first = (await book(c, course.id)).json()
    r = await book(c, course.id)
    assert r.status_code == 409 and r.json()["error"]["code"] == "ALREADY_BOOKED"
    assert (await c.post(f"{API}/bookings/{first['id']}/cancel")).status_code == 200
    assert (await book(c, course.id)).status_code == 201


async def test_idempotency_key_returns_same_booking(session, auth_client):
    course, _, c = await setup(session, auth_client)
    a = await book(c, course.id, "key-12345678")
    b = await book(c, course.id, "key-12345678")
    assert a.status_code == 201 and b.status_code == 200 and a.json()["id"] == b.json()["id"]
    assert (await session.execute(select(func.count()).select_from(Booking))).scalar_one() == 1
    other = await make_course(session)
    await session.commit()
    r = await book(c, other.id, "key-12345678")
    assert r.status_code == 422 and r.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


# --------------------------------------------------------------------------- CONCURRENCIA (crítico)


async def _race(session, auth_client, capacity: int, contenders: int):
    course = await make_course(session, capacity=capacity)
    users = [await make_user(session, role="CLIENT") for _ in range(contenders)]
    await session.commit()
    clients = [await auth_client(u) for u in users]
    responses = await asyncio.gather(*(book(c, course.id) for c in clients))
    return course, responses


async def test_last_seat_two_users_only_one_wins(session, auth_client):
    course, rs = await _race(session, auth_client, capacity=1, contenders=2)
    codes = sorted(r.status_code for r in rs)
    assert codes == [201, 409], [r.text for r in rs]
    assert (await session.execute(select(func.count()).select_from(Booking))).scalar_one() == 1


async def test_many_contenders_never_oversell(session, auth_client):
    for capacity, contenders in [(1, 25), (5, 30)]:
        course, rs = await _race(session, auth_client, capacity, contenders)
        ok = [r for r in rs if r.status_code == 201]
        full = [r for r in rs if r.status_code == 409 and r.json()["error"]["code"] == "COURSE_FULL"]
        assert len(ok) == capacity, f"capacidad {capacity}: {len(ok)} reservas creadas"
        assert len(ok) + len(full) == contenders  # nadie recibió un 500 ni otro error
        cid = course.id
        session.expire_all()
        held = (
            await session.execute(select(func.count()).select_from(Booking).where(Booking.course_id == cid))
        ).scalar_one()
        assert held == capacity


async def test_same_user_double_click_creates_single_booking(session, auth_client):
    course, _, c = await setup(session, auth_client)
    rs = await asyncio.gather(*(book(c, course.id) for _ in range(8)))
    assert sorted({r.status_code for r in rs}) == [201, 409]
    assert sum(r.status_code == 201 for r in rs) == 1
    assert (await session.execute(select(func.count()).select_from(Booking))).scalar_one() == 1


async def test_same_user_concurrent_with_same_idempotency_key(session, auth_client):
    course, _, c = await setup(session, auth_client)
    rs = await asyncio.gather(*(book(c, course.id, "same-key-0001") for _ in range(6)))
    assert all(r.status_code in (200, 201, 409) for r in rs)
    assert (await session.execute(select(func.count()).select_from(Booking))).scalar_one() == 1


# --------------------------------------------------------------------------- cancelación


async def test_cancel_frees_seat_and_records_history(session, auth_client):
    course, _, c = await setup(session, auth_client, capacity=1)
    b = (await book(c, course.id)).json()
    r = await c.post(f"{API}/bookings/{b['id']}/cancel", json={"reason": "no puedo ir"})
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED" and r.json()["next_action"] == "none"
    assert (await c.get(f"{API}/courses/{course.id}/availability")).json()["seats_available"] == 1
    detail = (await c.get(f"{API}/bookings/{b['id']}")).json()
    assert [(h["from_status"], h["to_status"]) for h in detail["history"]] == [
        (None, "PENDING_PAYMENT"),
        ("PENDING_PAYMENT", "CANCELLED"),
    ]


async def test_cancel_blocked_within_24h(session, auth_client):
    course, user, c = await setup(session, auth_client)
    b = (await book(c, course.id)).json()
    clock.freeze(course.starts_at - timedelta(hours=23))  # faltan 23 h
    r = await c.post(f"{API}/bookings/{b['id']}/cancel")
    assert r.status_code == 422 and r.json()["error"]["code"] == "CANCELLATION_WINDOW_CLOSED"
    assert (await c.get(f"{API}/bookings/{b['id']}")).json()["can_cancel"] is False


async def test_user_cannot_see_or_cancel_others_booking(session, auth_client):
    course, _, c1 = await setup(session, auth_client)
    intruder = await auth_client(await _new_client_user(session))
    b = (await book(c1, course.id)).json()
    assert (await intruder.get(f"{API}/bookings/{b['id']}")).status_code == 404
    assert (await intruder.post(f"{API}/bookings/{b['id']}/cancel")).status_code == 404
    assert (await intruder.get(f"{API}/bookings")).json()["total"] == 0
    assert (await c1.get(f"{API}/bookings")).json()["total"] == 1


async def _new_client_user(session):
    u = await make_user(session, role="CLIENT")
    await session.commit()
    return u


# --------------------------------------------------------------------------- caducidad


async def test_expired_hold_frees_seat_even_without_worker(session, auth_client):
    course, _, c = await setup(session, auth_client, capacity=1)
    await book(c, course.id)
    clock.freeze(clock.now() + timedelta(hours=25))  # pasa el plazo de pago; el job NO se ha ejecutado
    a = (await c.get(f"{API}/courses/{course.id}/availability")).json()
    assert a["seats_available"] == 1  # la disponibilidad ya lo sabe
    status = (await session.execute(select(Booking.status))).scalar_one()
    assert status == "PENDING_PAYMENT"  # sigue sin marcar...
    newcomer = await auth_client(await _new_client_user(session))
    assert (await book(newcomer, course.id)).status_code == 201  # ...y otra persona puede reservar


async def test_expire_job_marks_expired_and_is_idempotent(session, auth_client):
    course, _, c = await setup(session, auth_client)
    await book(c, course.id)
    assert await booking_service.expire_due_bookings(session) == 0  # aún en plazo
    clock.freeze(clock.now() + timedelta(hours=24, minutes=1))
    assert await booking_service.expire_due_bookings(session) == 1
    assert await booking_service.expire_due_bookings(session) == 0  # segunda ejecución: nada que hacer
    session.expire_all()
    assert (await session.execute(select(Booking.status))).scalar_one() == "EXPIRED"
    events = [
        e.event_type for e in (await session.execute(select(DomainEvent).order_by(DomainEvent.occurred_at))).scalars()
    ]
    assert "booking_expired" in events


async def test_user_can_rebook_after_own_hold_expired(session, auth_client):
    course, _, c = await setup(session, auth_client)
    await book(c, course.id)
    clock.freeze(clock.now() + timedelta(hours=25))
    assert (await book(c, course.id)).status_code == 201  # caduca el viejo y crea uno nuevo
    statuses = sorted((await session.execute(select(Booking.status))).scalars().all())
    assert statuses == ["EXPIRED", "PENDING_PAYMENT"]


# --------------------------------------------------------------------------- aprobación (admin)


async def paid_booking(session, auth_client, requires_approval=True):
    course, user, c = await setup(session, auth_client)
    course.requires_approval = requires_approval
    await session.commit()
    b = (await book(c, course.id)).json()
    await booking_service.on_payment_initiated(session, uuid.UUID(b["id"]))
    await session.commit()
    status = await booking_service.on_payment_confirmed(session, uuid.UUID(b["id"]))
    await session.commit()
    return course, c, b, status


async def test_payment_then_admin_approval_flow(session, auth_client):
    course, c, b, status = await paid_booking(session, auth_client)
    assert status.value == "PENDING_APPROVAL"
    assert (await c.get(f"{API}/bookings/{b['id']}")).json()["next_action"] == "wait_approval"
    admin = await auth_client(await make_user(session, role="ADMIN"))
    await session.commit()
    r = await admin.post(f"{API}/admin/bookings/{b['id']}/approve")
    assert r.status_code == 200 and r.json()["status"] == "CONFIRMED" and r.json()["user_email"]
    assert (await c.get(f"{API}/bookings/{b['id']}")).json()["next_action"] == "attend"
    hist = (
        (await session.execute(select(BookingStatusHistory.to_status).order_by(BookingStatusHistory.seq)))
        .scalars()
        .all()
    )
    assert hist == ["PENDING_PAYMENT", "PAYMENT_PROCESSING", "PAID", "PENDING_APPROVAL", "CONFIRMED"]


async def test_auto_approval_when_course_does_not_require_it(session, auth_client):
    *_, status = await paid_booking(session, auth_client, requires_approval=False)
    assert status.value == "CONFIRMED"


async def test_admin_cannot_approve_unpaid_booking(session, auth_client):
    course, _, c = await setup(session, auth_client)
    b = (await book(c, course.id)).json()
    admin = await auth_client(await make_user(session, role="ADMIN"))
    await session.commit()
    r = await admin.post(f"{API}/admin/bookings/{b['id']}/approve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


async def test_client_cannot_approve_or_list_all(session, auth_client):
    course, c, b, _ = await paid_booking(session, auth_client)
    assert (await c.post(f"{API}/admin/bookings/{b['id']}/approve")).status_code == 403
    assert (await c.get(f"{API}/admin/bookings")).status_code == 403


async def test_reject_requires_reason_and_frees_seat_flags_refund(session, auth_client):
    course, c, b, _ = await paid_booking(session, auth_client)
    admin = await auth_client(await make_user(session, role="ADMIN"))
    await session.commit()
    assert (await admin.post(f"{API}/admin/bookings/{b['id']}/reject", json={})).status_code == 422
    r = await admin.post(f"{API}/admin/bookings/{b['id']}/reject", json={"reason": "perfil no apto"})
    assert r.status_code == 200 and r.json()["status"] == "REJECTED"
    ev = (await session.execute(select(DomainEvent).where(DomainEvent.event_type == "booking_rejected"))).scalar_one()
    assert ev.payload["refund_required"] is True  # el Hito 6 gestionará el reembolso
    assert (await c.get(f"{API}/courses/{course.id}/availability")).json()["seats_taken"] == 0


async def test_admin_actions_are_audited(session, auth_client):
    course, c, b, _ = await paid_booking(session, auth_client)
    admin = await auth_client(await make_user(session, role="ADMIN"))
    await session.commit()
    await admin.post(f"{API}/admin/bookings/{b['id']}/approve")
    n = (await session.execute(text("SELECT count(*) FROM audit_logs WHERE action = 'booking.approved'"))).scalar_one()
    assert n == 1


async def test_cancel_course_cancels_all_bookings(session, auth_client):
    course, c, b, _ = await paid_booking(session, auth_client)  # una pagada (pendiente de aprobación)
    u2 = await make_user(session, role="CLIENT")
    await session.commit()
    await book(await auth_client(u2), course.id)  # otra sin pagar
    admin = await auth_client(await make_user(session, role="ADMIN"))
    await session.commit()
    r = await admin.post(f"{API}/admin/courses/{course.id}/cancel", json={"reason": "instructor enfermo"})
    assert r.status_code == 200 and r.json() == {"bookings_cancelled": 2}
    assert (await book(await auth_client(await _new_client_user(session)), course.id)).json()["error"][
        "code"
    ] == "COURSE_CANCELLED"
    session.expire_all()
    assert set((await session.execute(select(Booking.status))).scalars()) == {"CANCELLED"}
    refunds = (
        (await session.execute(select(DomainEvent).where(DomainEvent.event_type == "course_cancelled"))).scalars().all()
    )
    assert len(refunds) >= 1
    paid_cancel = [
        e
        for e in (await session.execute(select(DomainEvent))).scalars()
        if e.payload.get("refund_required") and e.payload.get("booking_id") == b["id"]
    ]
    assert len(paid_cancel) == 1  # solo la reserva pagada necesita reembolso
