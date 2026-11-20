import asyncio
import time
from datetime import timedelta

import pytest
from sqlalchemy import func, select, text

from app.core import clock
from app.modules.bookings.models import Booking
from app.modules.core_events.models import DomainEvent
from app.modules.payments.models import Commission, Payment, PaymentEvent
from app.modules.payments.provider import FakePaymentProvider, ProviderEventType, get_provider, sign
from tests.factories import make_course, make_user
from tests.integration.test_bookings import book

API = "/api/v1"
OK, FAIL = ProviderEventType.SUCCEEDED, ProviderEventType.FAILED


@pytest.fixture(autouse=True)
def _provider():
    p = get_provider()
    assert isinstance(p, FakePaymentProvider)
    p.ledger.clear()
    p.refunds.clear()
    return p


async def post_webhook(client, body, headers):
    return await client.post(f"{API}/payments/webhooks/fake", content=body, headers=headers)


async def booked(session, auth_client, **course_kw):
    course = await make_course(session, **course_kw)
    user = await make_user(session, role="CLIENT")
    await session.commit()
    c = await auth_client(user)
    b = (await book(c, course.id)).json()
    return course, user, c, b


async def started(session, auth_client, **kw):
    course, user, c, b = await booked(session, auth_client, **kw)
    r = await c.post(f"{API}/bookings/{b['id']}/pay")
    assert r.status_code == 200, r.text
    return course, user, c, b, r.json()


async def reference_of(session, payment_id) -> str:
    return (await session.execute(select(Payment.transaction_reference).where(Payment.id == payment_id))).scalar_one()


async def paid(session, auth_client, _provider, **kw):
    course, user, c, b, p = await started(session, auth_client, **kw)
    ref = await reference_of(session, p["id"])
    body, headers = _provider.build_webhook(OK, ref)
    assert (await post_webhook(c, body, headers)).json() == {"status": "processed"}
    return course, user, c, b, p, ref


async def test_start_payment_moves_booking_to_processing_and_is_idempotent(session, auth_client):
    _, _, c, b, p = await started(session, auth_client)
    assert p["status"] == "PROCESSING" and p["checkout_url"] and p["amount_minor"] == b["price_minor"]
    again = (await c.post(f"{API}/bookings/{b['id']}/pay")).json()
    assert again["id"] == p["id"]  # doble clic: mismo pago
    assert (await session.execute(select(func.count()).select_from(Payment))).scalar_one() == 1
    assert (await c.get(f"{API}/bookings/{b['id']}")).json()["next_action"] == "wait_payment"


async def test_cannot_pay_someone_elses_booking(session, auth_client):
    _, _, _, b = await booked(session, auth_client)
    intruder = await auth_client(await make_user(session, role="CLIENT"))
    await session.commit()
    assert (await intruder.post(f"{API}/bookings/{b['id']}/pay")).status_code == 404


async def test_cannot_pay_after_window_expired(session, auth_client):
    _, _, c, b = await booked(session, auth_client)
    clock.freeze(clock.now() + timedelta(hours=25))
    r = await c.post(f"{API}/bookings/{b['id']}/pay")
    assert r.status_code == 422 and r.json()["error"]["code"] == "PAYMENT_WINDOW_EXPIRED"


async def test_successful_payment_flow_with_commission_snapshot(session, auth_client, _provider):
    course, _, c, b, p, ref = await paid(session, auth_client, _provider, price_minor=100_000)
    got = (await c.get(f"{API}/bookings/{b['id']}")).json()
    assert got["status"] == "PENDING_APPROVAL" and got["next_action"] == "wait_approval"
    assert (await c.get(f"{API}/payments")).json()["items"][0]["status"] == "PAID"
    com = (await session.execute(select(Commission))).scalar_one()
    assert (com.gross_minor, com.commission_minor, com.net_minor, com.commission_bps) == (100_000, 20_000, 80_000, 2000)
    assert (
        await session.execute(select(DomainEvent).where(DomainEvent.event_type == "payment_completed"))
    ).scalar_one()
    n = (
        await session.execute(text("SELECT count(*) FROM audit_logs WHERE action = 'payment.status_changed'"))
    ).scalar_one()
    assert n == 2  # PENDING→PROCESSING, PROCESSING→PAID


async def test_dev_simulation_endpoint(session, auth_client):
    _, _, c, b, p = await started(session, auth_client)
    ref = await reference_of(session, p["id"])
    r = await c.post(f"{API}/dev/payments/{ref}/simulate?outcome=success")
    assert r.json() == {"status": "processed"}
    assert (await c.get(f"{API}/bookings/{b['id']}")).json()["status"] == "PENDING_APPROVAL"


# ----------------------------------------------------------------------------- seguridad del webhook


async def test_webhook_rejects_bad_signature_and_tampering(session, auth_client, client, _provider):
    _, _, c, b, p = await started(session, auth_client)
    ref = await reference_of(session, p["id"])
    body, headers = _provider.build_webhook(OK, ref)
    forged = dict(headers, **{"x-signature": "sha256=" + "0" * 64})
    assert (await post_webhook(client, body, forged)).status_code == 401
    tampered = body.replace(b"payment.succeeded", b"payment.succeedes")
    assert (await post_webhook(client, tampered, headers)).status_code == 401
    assert (await post_webhook(client, body, {})).status_code == 401
    assert (await session.execute(select(func.count()).select_from(PaymentEvent))).scalar_one() == 0
    assert (await c.get(f"{API}/bookings/{b['id']}")).json()["status"] == "PAYMENT_PROCESSING"  # nada cambió


async def test_webhook_rejects_replay_of_old_timestamp(session, auth_client, client, _provider):
    _, _, _, _, p = await started(session, auth_client)
    ref = await reference_of(session, p["id"])
    body, _ = _provider.build_webhook(OK, ref)
    old = str(int(time.time()) - 3600)
    from app.core.config import get_settings

    headers = {"x-timestamp": old, "x-signature": "sha256=" + sign(get_settings().payment_webhook_secret, old, body)}
    assert (await post_webhook(client, body, headers)).status_code == 401


async def test_duplicate_webhook_is_idempotent(session, auth_client, _provider):
    _, _, c, b, p = await started(session, auth_client)
    ref = await reference_of(session, p["id"])
    body, headers = _provider.build_webhook(OK, ref, event_id="evt-1")
    assert (await post_webhook(c, body, headers)).json() == {"status": "processed"}
    assert (await post_webhook(c, body, headers)).json() == {"status": "duplicate"}
    assert (await session.execute(select(func.count()).select_from(Commission))).scalar_one() == 1
    assert (await session.execute(select(func.count()).select_from(PaymentEvent))).scalar_one() == 1


async def test_same_event_concurrently_is_applied_once(session, auth_client, _provider):
    _, _, c, _, p = await started(session, auth_client)
    ref = await reference_of(session, p["id"])
    body, headers = _provider.build_webhook(OK, ref, event_id="evt-race")
    rs = await asyncio.gather(*(post_webhook(c, body, headers) for _ in range(8)))
    assert all(r.status_code == 200 for r in rs), [r.text for r in rs]
    assert sorted(r.json()["status"] for r in rs).count("processed") == 1
    assert (await session.execute(select(func.count()).select_from(Commission))).scalar_one() == 1


async def test_second_success_event_with_new_id_does_not_duplicate_effects(session, auth_client, _provider):
    _, _, c, _, p, ref = await paid(session, auth_client, _provider)
    body, headers = _provider.build_webhook(OK, ref, event_id="another-id")
    await post_webhook(c, body, headers)
    assert (await session.execute(select(func.count()).select_from(Commission))).scalar_one() == 1


async def test_unknown_reference_is_ignored_not_error(session, auth_client, _provider, client):
    _provider.ledger["ghost"] = __import__("app.modules.payments.provider", fromlist=["x"]).ProviderStatus(
        "PAID", 1, "COP"
    )
    body, headers = _provider.build_webhook(OK, "ghost")
    r = await post_webhook(client, body, headers)
    assert r.status_code == 200 and r.json() == {"status": "ignored"}


async def test_amount_mismatch_is_rejected(session, auth_client, _provider):
    _, _, c, b, p = await started(session, auth_client)
    ref = await reference_of(session, p["id"])
    st = _provider.ledger[ref]
    _provider.ledger[ref] = type(st)("PENDING", 1, st.currency)  # el proveedor "cobró" 1 centavo
    body, headers = _provider.build_webhook(OK, ref)
    assert (await post_webhook(c, body, headers)).json() == {"status": "rejected"}
    assert (await c.get(f"{API}/bookings/{b['id']}")).json()["status"] == "PAYMENT_PROCESSING"
    assert (await session.execute(select(func.count()).select_from(Commission))).scalar_one() == 0


async def test_success_event_not_confirmed_by_provider_is_ignored(session, auth_client, _provider):
    _, _, c, b, p = await started(session, auth_client)
    ref = await reference_of(session, p["id"])
    body, headers = _provider.build_webhook(OK, ref)
    _provider.ledger[ref] = type(_provider.ledger[ref])("PENDING", _provider.ledger[ref].amount_minor, "COP")
    assert (await post_webhook(c, body, headers)).json() == {"status": "ignored"}
    assert (await c.get(f"{API}/bookings/{b['id']}")).json()["status"] == "PAYMENT_PROCESSING"


# ----------------------------------------------------------------------------- fallos y reintentos


async def test_failed_payment_returns_booking_to_pending_and_allows_retry(session, auth_client, _provider):
    _, _, c, b, p = await started(session, auth_client)
    ref = await reference_of(session, p["id"])
    body, headers = _provider.build_webhook(FAIL, ref)
    await post_webhook(c, body, headers)
    got = (await c.get(f"{API}/bookings/{b['id']}")).json()
    assert got["status"] == "PENDING_PAYMENT" and got["next_action"] == "pay"
    retry = await c.post(f"{API}/bookings/{b['id']}/pay")
    assert retry.status_code == 200 and retry.json()["id"] != p["id"] and retry.json()["status"] == "PROCESSING"
    statuses = sorted((await session.execute(select(Payment.status))).scalars().all())
    assert statuses == ["FAILED", "PROCESSING"]


async def test_late_failure_does_not_undo_a_paid_payment(session, auth_client, _provider):
    _, _, c, b, p, ref = await paid(session, auth_client, _provider)
    body, headers = _provider.build_webhook(FAIL, ref)
    await post_webhook(c, body, headers)
    assert (await session.execute(select(Payment.status))).scalar_one() == "PAID"


async def test_provider_outage_leaves_booking_payable(session, auth_client, _provider, monkeypatch):
    _, _, c, b = await booked(session, auth_client)

    async def boom(*a, **k):
        raise RuntimeError("proveedor caído")

    monkeypatch.setattr(_provider, "create_checkout", boom)
    r = await c.post(f"{API}/bookings/{b['id']}/pay")
    assert r.status_code == 502 and r.json()["error"]["code"] == "EXTERNAL_SERVICE_ERROR"
    assert "caído" not in r.text
    assert (await c.get(f"{API}/bookings/{b['id']}")).json()["status"] == "PENDING_PAYMENT"
    monkeypatch.undo()
    assert (await c.post(f"{API}/bookings/{b['id']}/pay")).status_code == 200  # se puede reintentar


async def test_late_payment_after_expiry_does_not_confirm_and_flags_refund(session, auth_client, _provider):
    course, _, c, b, p = await started(session, auth_client)
    ref = await reference_of(session, p["id"])
    # El pago queda "en proceso" pero la reserva se cancela antes de que llegue el webhook (p. ej. por el admin al cancelar el curso).
    admin = await auth_client(await make_user(session, role="ADMIN"))
    await session.commit()
    await admin.post(f"{API}/admin/courses/{course.id}/cancel", json={"reason": "instructor enfermo"})
    body, headers = _provider.build_webhook(OK, ref)
    assert (await post_webhook(c, body, headers)).json() == {"status": "processed"}
    assert (await session.execute(select(Booking.status))).scalar_one() == "CANCELLED"
    assert (await session.execute(select(func.count()).select_from(Commission))).scalar_one() == 0
    ev = (
        await session.execute(select(DomainEvent).where(DomainEvent.event_type == "payment_needs_refund"))
    ).scalar_one()
    assert ev.payload["booking_status"] == "CANCELLED"


# ----------------------------------------------------------------------------- reembolso


async def test_refund_flow(session, auth_client, _provider):
    course, _, c, b, p, ref = await paid(session, auth_client, _provider)
    admin = await auth_client(await make_user(session, role="ADMIN"))
    await session.commit()
    # sin cerrar la reserva, no se reembolsa (política P-05 pendiente)
    r = await admin.post(f"{API}/admin/payments/{p['id']}/refund", json={"reason": "cliente lo pide"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "REFUND_NOT_ALLOWED"
    await admin.post(f"{API}/admin/bookings/{b['id']}/reject", json={"reason": "perfil no apto"})
    r = await admin.post(f"{API}/admin/payments/{p['id']}/refund", json={"reason": "rechazada"})
    assert r.status_code == 200 and r.json()["status"] == "REFUNDED"
    assert (await c.get(f"{API}/bookings/{b['id']}")).json()["status"] == "REFUNDED"
    assert (await session.execute(select(Commission.status))).scalar_one() == "REVERSED"
    assert _provider.refunds == [(ref, b["price_minor"])]
    assert (await admin.post(f"{API}/admin/payments/{p['id']}/refund", json={"reason": "otra vez"})).status_code == 409


async def test_client_cannot_refund_or_see_all_payments(session, auth_client, _provider):
    _, _, c, b, p, _ = await paid(session, auth_client, _provider)
    assert (await c.post(f"{API}/admin/payments/{p['id']}/refund", json={"reason": "yo quiero"})).status_code == 403
    assert (await c.get(f"{API}/admin/payments")).status_code == 403
    assert (await c.get(f"{API}/admin/commissions")).status_code == 403


# ----------------------------------------------------------------------------- comisión configurable y curso gratuito


async def test_commission_rate_is_configurable_and_snapshotted(session, auth_client, _provider):
    owner = await auth_client(await make_user(session, role="OWNER"))
    await session.commit()
    assert (await owner.get(f"{API}/admin/settings/commission")).json() == {"commission_bps": 2000}
    assert (await owner.put(f"{API}/admin/settings/commission", json={"commission_bps": 10_001})).status_code == 422
    assert (await owner.put(f"{API}/admin/settings/commission", json={"commission_bps": 1500})).json() == {
        "commission_bps": 1500
    }
    await paid(session, auth_client, _provider, price_minor=100_000)
    com = (await session.execute(select(Commission))).scalar_one()
    assert (com.commission_minor, com.net_minor, com.commission_bps) == (15_000, 85_000, 1500)
    await owner.put(f"{API}/admin/settings/commission", json={"commission_bps": 3000})
    session.expire_all()
    assert (await session.execute(select(Commission.commission_bps))).scalar_one() == 1500  # el pasado no se reescribe
    summary = (await owner.get(f"{API}/admin/commissions")).json()
    assert summary["totals_by_currency"]["COP"] == {
        "gross_minor": 100_000,
        "commission_minor": 15_000,
        "net_minor": 85_000,
    }


async def test_only_owner_changes_commission(session, auth_client):
    admin = await auth_client(await make_user(session, role="ADMIN"))
    await session.commit()
    assert (await admin.put(f"{API}/admin/settings/commission", json={"commission_bps": 500})).status_code == 403
    assert (await admin.get(f"{API}/admin/commissions")).status_code == 403  # comisiones: solo propietario


async def test_free_course_confirms_without_provider(session, auth_client):
    _, _, c, b = await booked(session, auth_client, price_minor=0)
    r = await c.post(f"{API}/bookings/{b['id']}/pay")
    assert r.status_code == 200 and r.json()["status"] == "PAID" and r.json()["provider"] == "none"
    assert (await c.get(f"{API}/bookings/{b['id']}")).json()["status"] == "PENDING_APPROVAL"
    assert (await session.execute(select(Commission.commission_minor))).scalar_one() == 0


async def test_no_card_data_columns_exist(session):
    cols = (
        (
            await session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name IN ('payments','payment_events')"
                )
            )
        )
        .scalars()
        .all()
    )
    assert not any(k in c for c in cols for k in ("card", "cvv", "pan"))
