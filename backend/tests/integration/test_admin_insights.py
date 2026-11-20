from tests.factories import make_course, make_user
from tests.integration.test_bookings import book
from tests.integration.test_courses import base_refs  # noqa: F401

API = "/api/v1"


async def test_audit_logs_owner_only_and_filterable(session, auth_client):
    owner = await auth_client(await make_user(session, role="OWNER"))
    admin = await auth_client(await make_user(session, role="ADMIN"))
    await session.commit()
    await owner.put(f"{API}/admin/settings/commission", json={"commission_bps": 1800})
    assert (await admin.get(f"{API}/admin/audit-logs")).status_code == 403
    r = (await owner.get(f"{API}/admin/audit-logs?action=settings.commission_changed")).json()
    assert r["total"] == 1 and r["items"][0]["changes"] == {"from": 2000, "to": 1800}
    assert r["items"][0]["actor_user_id"]


async def test_metrics_hide_money_from_plain_admin(session, auth_client):
    course = await make_course(session, capacity=4)
    client_user = await make_user(session, role="CLIENT")
    owner = await auth_client(await make_user(session, role="OWNER"))
    admin = await auth_client(await make_user(session, role="ADMIN"))
    await session.commit()
    await book(await auth_client(client_user), course.id)
    m = (await admin.get(f"{API}/admin/metrics")).json()
    assert m["bookings_by_status"] == {"PENDING_PAYMENT": 1} and m["pending_payment"] == 1
    assert m["upcoming_courses"][0]["seats_taken"] == 1 and m["upcoming_courses"][0]["occupancy_pct"] == 25
    assert "revenue_by_currency" not in m  # dinero: solo propietario
    assert "revenue_by_currency" in (await owner.get(f"{API}/admin/metrics")).json()


async def test_clients_cannot_read_metrics(session, auth_client):
    c = await auth_client(await make_user(session, role="CLIENT"))
    await session.commit()
    assert (await c.get(f"{API}/admin/metrics")).status_code == 403
