import asyncio

import pytest
from sqlalchemy import func, select

from app.bootstrap import ensure_owner
from app.core.config import get_settings
from app.main import create_app
from app.modules.auth.models import User
from app.modules.notifications.models import Notification
from app.worker.__main__ import worker_loop
from tests.factories import make_course, make_user
from tests.integration.test_bookings import book


async def test_bootstrap_creates_owner_once_and_can_log_in(session, client):
    assert await ensure_owner("dueno@tallerya.co", "una-clave-larga-123") is True
    assert await ensure_owner("otro@tallerya.co", "una-clave-larga-123") is False  # ya existe un propietario
    assert (await session.execute(select(func.count()).select_from(User))).scalar_one() == 1
    r = await client.post("/api/v1/auth/login", json={"email": "dueno@tallerya.co", "password": "una-clave-larga-123"})
    assert r.status_code == 200 and r.json()["roles"] == ["OWNER"]


async def test_bootstrap_rejects_weak_password(session):
    assert await ensure_owner("dueno@tallerya.co", "corta") is False
    assert (await session.execute(select(func.count()).select_from(User))).scalar_one() == 0


async def test_worker_loop_processes_events_and_stops_cleanly(session, auth_client):
    course = await make_course(session)
    user = await make_user(session, role="CLIENT")
    await session.commit()
    await book(await auth_client(user), course.id)
    stop = asyncio.Event()
    task = asyncio.create_task(worker_loop(stop))
    for _ in range(40):  # hasta ~4 s
        await asyncio.sleep(0.1)
        session.expire_all()
        if (await session.execute(select(func.count()).select_from(Notification))).scalar_one() >= 1:
            break
    stop.set()
    await asyncio.wait_for(task, timeout=10)
    assert (await session.execute(select(func.count()).select_from(Notification))).scalar_one() >= 1


async def test_api_lifespan_runs_embedded_worker_when_enabled(session, auth_client, monkeypatch):
    monkeypatch.setenv("EMBEDDED_WORKER", "true")
    get_settings.cache_clear()
    try:
        course = await make_course(session)
        user = await make_user(session, role="CLIENT")
        await session.commit()
        await book(await auth_client(user), course.id)
        app = create_app()
        async with app.router.lifespan_context(app):
            for _ in range(40):
                await asyncio.sleep(0.1)
                session.expire_all()
                if (await session.execute(select(func.count()).select_from(Notification))).scalar_one() >= 1:
                    break
        assert (await session.execute(select(func.count()).select_from(Notification))).scalar_one() >= 1
    finally:
        monkeypatch.delenv("EMBEDDED_WORKER")
        get_settings.cache_clear()


@pytest.mark.parametrize("value", ["", "false"])
async def test_embedded_worker_off_by_default(value):
    assert get_settings().embedded_worker is False
