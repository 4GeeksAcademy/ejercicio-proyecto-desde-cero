import uuid
from datetime import timedelta

from sqlalchemy import func, select, text

from app.core import clock
from app.modules.analytics import pipeline
from app.modules.analytics.models import AnalyticsEvent, DailyCourseMetrics
from app.modules.core_events.models import DomainEvent
from app.modules.payments.provider import ProviderEventType, get_provider
from app.worker import jobs
from tests.factories import make_course, make_user
from tests.integration.test_bookings import book
from tests.integration.test_payments import post_webhook, reference_of

API = "/api/v1"


async def totals(session):
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(DailyCourseMetrics.course_views), 0),
                func.coalesce(func.sum(DailyCourseMetrics.bookings_created), 0),
                func.coalesce(func.sum(DailyCourseMetrics.bookings_confirmed), 0),
                func.coalesce(func.sum(DailyCourseMetrics.payments_completed), 0),
                func.coalesce(func.sum(DailyCourseMetrics.bookings_expired), 0),
            )
        )
    ).one()
    return tuple(int(x) for x in row)  # views, created, confirmed, paid, expired


async def run_flow(session, auth_client):
    course = await make_course(session)
    user = await make_user(session, role="CLIENT")
    admin = await make_user(session, role="ADMIN")
    await session.commit()
    c, a = await auth_client(user), await auth_client(admin)
    await c.post(f"{API}/courses/{course.id}/view")
    await c.post(f"{API}/courses/{course.id}/view")
    b = (await book(c, course.id)).json()
    p = (await c.post(f"{API}/bookings/{b['id']}/pay")).json()
    fake = get_provider()
    body, headers = fake.build_webhook(ProviderEventType.SUCCEEDED, await reference_of(session, p["id"]))
    await post_webhook(c, body, headers)
    await a.post(f"{API}/admin/bookings/{b['id']}/approve")
    return course, a


async def test_pipeline_aggregates_events_into_metrics(session, auth_client):
    course, admin = await run_flow(session, auth_client)
    await jobs.process_outbox(session)
    assert await totals(session) == (2, 1, 1, 1, 0)
    data = (await admin.get(f"{API}/admin/analytics?days=7")).json()
    row = data["by_course"][0]
    assert row["course_id"] == str(course.id) and row["views"] == 2 and row["created"] == 1 and row["confirmed"] == 1
    assert row["view_to_booking_pct"] == 50 and row["confirmation_pct"] == 100
    assert len(data["series"]) == 1


async def test_pipeline_is_idempotent_and_rebuildable(session, auth_client):
    await run_flow(session, auth_client)
    await jobs.process_outbox(session)
    before = await totals(session)
    # Reprocesar los mismos eventos NO duplica.
    for ev in (await session.execute(select(DomainEvent))).scalars():
        assert await pipeline.consume(session, ev) is False
    await session.commit()
    assert await totals(session) == before
    # Reconstruir desde cero reproduce exactamente lo mismo.
    await pipeline.rebuild(session)
    assert await totals(session) == before


async def test_events_without_course_or_invalid_are_ignored(session):
    ev = DomainEvent(
        event_type="booking_created",
        aggregate_type="booking",
        aggregate_id=uuid.uuid4(),
        payload={"booking_id": str(uuid.uuid4())},
    )
    session.add(ev)
    await session.commit()
    assert await pipeline.consume(session, ev) is False
    assert (await session.execute(select(func.count()).select_from(AnalyticsEvent))).scalar_one() == 0


async def test_expired_counts_and_analytics_contain_no_personal_data(session, auth_client):
    course = await make_course(session)
    user = await make_user(session, role="CLIENT")
    await session.commit()
    await book(await auth_client(user), course.id)
    clock.freeze(clock.now() + timedelta(hours=25))
    from app.worker.__main__ import run_cycle

    await run_cycle()
    await run_cycle()
    assert (await totals(session))[4] == 1
    cols = (
        (
            await session.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_schema = 'analytics'")
            )
        )
        .scalars()
        .all()
    )
    assert not any(k in c for c in cols for k in ("user", "email", "name", "phone", "ip"))


async def test_view_endpoint_only_for_public_courses_and_admin_only_read(session, auth_client):
    draft = await make_course(session, status="DRAFT")
    user = await make_user(session, role="CLIENT")
    await session.commit()
    c = await auth_client(user)
    assert (await c.post(f"{API}/courses/{draft.id}/view")).status_code == 404
    assert (await c.get(f"{API}/admin/analytics")).status_code == 403
