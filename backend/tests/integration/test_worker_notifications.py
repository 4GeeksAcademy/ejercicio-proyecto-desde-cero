import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.core import clock
from app.core.mail import InMemoryMailer
from app.modules.bookings import qr
from app.modules.bookings.models import Booking
from app.modules.core_events.models import DomainEvent
from app.modules.notifications.models import Notification
from app.modules.notifications.service import deliver_pending_emails
from app.modules.payments.provider import FakePaymentProvider, ProviderEventType, get_provider
from app.worker import jobs
from app.worker.__main__ import run_cycle
from tests.factories import make_course, make_user
from tests.integration.test_bookings import book
from tests.integration.test_payments import post_webhook, reference_of

API = "/api/v1"


@pytest.fixture(autouse=True)
def _fake():
    p = get_provider()
    assert isinstance(p, FakePaymentProvider)
    p.ledger.clear()
    return p


async def setup_booking(session, auth_client, locale="es", **course_kw):
    course = await make_course(session, **course_kw)
    user = await make_user(session, role="CLIENT")
    user.profile.preferred_locale = locale
    await session.commit()
    c = await auth_client(user)
    return course, user, c, (await book(c, course.id)).json()


async def pay_and_confirm(session, auth_client, _fake, **kw):
    course, user, c, b = await setup_booking(session, auth_client, **kw)
    p = (await c.post(f"{API}/bookings/{b['id']}/pay")).json()
    body, headers = _fake.build_webhook(ProviderEventType.SUCCEEDED, await reference_of(session, p["id"]))
    await post_webhook(c, body, headers)
    return course, user, c, b


async def test_outbox_creates_inapp_and_email_notifications(session, auth_client, mailer):
    _, _, c, b = await setup_booking(session, auth_client)
    assert await jobs.process_outbox(session) >= 1
    inbox = (await c.get(f"{API}/notifications")).json()
    assert inbox["total"] == 1 and inbox["unread"] == 1
    assert inbox["items"][0]["kind"] == "booking_created" and "Cerámica" in inbox["items"][0]["title"]
    assert inbox["items"][0]["booking_id"] == b["id"]
    sent, failed = await deliver_pending_emails(session, mailer)
    assert (sent, failed) == (1, 0) and len(mailer.sent) == 1
    assert mailer.sent[0].subject.startswith("Reserva creada")


async def test_english_users_get_english_messages(session, auth_client, mailer):
    await setup_booking(session, auth_client, locale="en")
    await jobs.process_outbox(session)
    await deliver_pending_emails(session, mailer)
    assert mailer.sent[0].subject.startswith("Booking created")


async def test_processing_outbox_twice_does_not_duplicate(session, auth_client):
    await setup_booking(session, auth_client)
    await jobs.process_outbox(session)
    assert await jobs.process_outbox(session) == 0
    assert (await session.execute(select(func.count()).select_from(Notification))).scalar_one() == 2  # in_app + email


async def test_email_failure_never_breaks_booking_and_retries(session, auth_client):
    _, _, c, b = await setup_booking(session, auth_client)
    await jobs.process_outbox(session)

    class Broken:
        async def send(self, mail):
            raise ConnectionError("smtp caído con datos privados")

    assert await deliver_pending_emails(session, Broken()) == (0, 1)
    n = (await session.execute(select(Notification).where(Notification.channel == "email"))).scalar_one()
    assert n.status == "PENDING" and n.attempts == 1 and n.last_error == "ConnectionError"  # sin detalle sensible
    assert "privados" not in (n.last_error or "")
    assert (await c.get(f"{API}/bookings/{b['id']}")).json()["status"] == "PENDING_PAYMENT"  # la reserva sigue intacta
    assert await deliver_pending_emails(session, Broken()) == (0, 0)  # backoff: aún no toca reintentar
    clock.freeze(clock.now() + timedelta(minutes=2))
    mailer = InMemoryMailer()
    assert await deliver_pending_emails(session, mailer) == (1, 0)  # el servicio se recuperó


async def test_email_marked_failed_after_max_attempts(session, auth_client):
    await setup_booking(session, auth_client)
    await jobs.process_outbox(session)

    class Broken:
        async def send(self, mail):
            raise ConnectionError

    for _i in range(6):
        clock.freeze(clock.now() + timedelta(hours=1))
        await deliver_pending_emails(session, Broken())
    n = (await session.execute(select(Notification).where(Notification.channel == "email"))).scalar_one()
    assert n.status == "FAILED" and n.attempts == 5


async def test_poison_event_does_not_block_others(session, auth_client):
    await setup_booking(session, auth_client)
    session.add(
        DomainEvent(
            event_type="booking_created",
            aggregate_type="booking",
            aggregate_id=uuid.uuid4(),
            payload={"booking_id": str(uuid.uuid4())},
        )
    )
    await session.commit()
    assert await jobs.process_outbox(session) == 1  # el válido se procesó
    bad = (await session.execute(select(DomainEvent).where(DomainEvent.attempts > 0))).scalar_one()
    assert bad.attempts == 1 and bad.processed_at is None and bad.last_error == "LookupError"
    for _ in range(6):
        await jobs.process_outbox(session)
    session.expire_all()
    assert (
        await session.execute(select(DomainEvent.attempts).where(DomainEvent.last_error.is_not(None)))
    ).scalar_one() == 5  # aparcado


async def test_email_preference_is_respected(session, auth_client):
    course, user, c, b = await setup_booking(session, auth_client)
    assert (await c.put(f"{API}/notifications/preferences", json={"email_enabled": False})).json()[
        "email_enabled"
    ] is False
    await jobs.process_outbox(session)
    channels = (await session.execute(select(Notification.channel))).scalars().all()
    assert channels == ["in_app"]


async def test_payment_notifies_client_and_staff_then_approval_issues_qr(session, auth_client, mailer, _fake):
    staff = await make_user(session, role="ADMIN")
    await session.commit()
    course, user, c, b = await pay_and_confirm(session, auth_client, _fake)
    await jobs.process_outbox(session)
    admin = await auth_client(staff)
    kinds = [n["kind"] for n in (await admin.get(f"{API}/notifications")).json()["items"]]
    assert "admin_pending_approval" in kinds
    assert "payment_completed" in [n["kind"] for n in (await c.get(f"{API}/notifications")).json()["items"]]
    assert (await c.get(f"{API}/bookings/{b['id']}/qr")).status_code == 409  # aún no confirmada
    assert (await admin.post(f"{API}/admin/bookings/{b['id']}/approve")).status_code == 200
    await jobs.process_outbox(session)
    assert "booking_approved" in [n["kind"] for n in (await c.get(f"{API}/notifications")).json()["items"]]
    assert (await c.get(f"{API}/bookings/{b['id']}/qr")).status_code == 200


async def test_worker_cycle_expires_bookings_and_notifies(session, auth_client, mailer):
    from app.core.mail import set_mailer

    set_mailer(mailer)
    _, _, c, b = await setup_booking(session, auth_client)
    clock.freeze(clock.now() + timedelta(hours=25))
    first = await run_cycle()
    assert first["expired"] == 1
    session.expire_all()
    assert (await session.execute(select(Booking.status))).scalar_one() == "EXPIRED"
    await run_cycle()  # el evento booking_expired genera el aviso
    kinds = [n["kind"] for n in (await c.get(f"{API}/notifications")).json()["items"]]
    assert "booking_expired" in kinds
    assert any(m.subject.startswith("Reserva caducada") for m in mailer.sent)


async def test_reminder_sent_once(session, auth_client):
    course, user, c, b = await setup_booking(session, auth_client)
    session.add(await _confirm(session, b["id"]))
    await session.commit()
    clock.freeze(course.starts_at - timedelta(hours=20))
    assert await jobs.send_reminders(session) == 1
    await jobs.send_reminders(session)  # se ejecuta de nuevo: no duplica
    n = (
        await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.type == "booking_reminder", Notification.channel == "in_app")
        )
    ).scalar_one()
    assert n == 1


async def _confirm(session, booking_id):
    b = await session.get(Booking, uuid.UUID(booking_id))
    b.status = "CONFIRMED"
    return b


async def test_mark_notification_read_and_isolation(session, auth_client):
    _, _, c, _ = await setup_booking(session, auth_client)
    await jobs.process_outbox(session)
    nid = (await c.get(f"{API}/notifications")).json()["items"][0]["id"]
    other = await auth_client(await make_user(session, role="CLIENT"))
    await session.commit()
    assert (await other.patch(f"{API}/notifications/{nid}/read")).status_code == 404
    assert (await c.patch(f"{API}/notifications/{nid}/read")).status_code == 204
    assert (await c.get(f"{API}/notifications")).json()["unread"] == 0


# ----------------------------------------------------------------------------- QR y check-in


async def confirmed_booking(session, auth_client, _fake):
    course, user, c, b = await pay_and_confirm(session, auth_client, _fake)
    admin = await auth_client(await make_user(session, role="ADMIN"))
    await session.commit()
    await admin.post(f"{API}/admin/bookings/{b['id']}/approve")
    return course, user, c, b, admin


async def test_qr_token_has_no_personal_data_and_cannot_be_forged(session, auth_client, _fake):
    course, user, c, b, admin = await confirmed_booking(session, auth_client, _fake)
    token = (await c.get(f"{API}/bookings/{b['id']}/qr")).json()["token"]
    assert user.email not in token and "Test User" not in token
    assert str(qr.parse_token(token)) == b["id"]
    forged = token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB")
    assert (await admin.post(f"{API}/admin/checkin", json={"token": forged})).status_code == 422
    assert (await admin.post(f"{API}/admin/checkin", json={"token": "basura-total-sin-formato"})).status_code == 422


async def test_other_user_cannot_get_my_qr(session, auth_client, _fake):
    _, _, _, b, _ = await confirmed_booking(session, auth_client, _fake)
    other = await auth_client(await make_user(session, role="CLIENT"))
    await session.commit()
    assert (await other.get(f"{API}/bookings/{b['id']}/qr")).status_code == 404


async def test_checkin_is_idempotent_and_windowed(session, auth_client, _fake):
    course, _, c, b, admin = await confirmed_booking(session, auth_client, _fake)
    token = (await c.get(f"{API}/bookings/{b['id']}/qr")).json()["token"]
    r = await admin.post(f"{API}/admin/checkin", json={"token": token})
    assert r.status_code == 422 and r.json()["error"]["code"] == "CHECKIN_OUT_OF_WINDOW"  # faltan 72 h
    clock.freeze(course.starts_at - timedelta(minutes=10))
    first = (await admin.post(f"{API}/admin/checkin", json={"token": token})).json()
    again = (await admin.post(f"{API}/admin/checkin", json={"token": token})).json()
    assert first["first_time"] is True and again["first_time"] is False
    assert (await c.post(f"{API}/admin/checkin", json={"token": token})).status_code == 403  # un cliente no puede
