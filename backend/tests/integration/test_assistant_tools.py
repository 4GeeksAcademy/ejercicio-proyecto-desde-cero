import json

from sqlalchemy import func, select

from app.modules.assistant.tools import READ_ONLY_TOOLS, TOOL_DEFINITIONS, execute_tool
from app.modules.bookings.models import Booking
from tests.factories import make_course, make_user


async def test_only_read_only_tools_exist():
    assert READ_ONLY_TOOLS == {"search_courses", "get_course_details", "check_availability"}
    assert not any(w in t["name"] for t in TOOL_DEFINITIONS for w in ("book", "pay", "cancel", "refund", "reserve"))
    json.dumps(TOOL_DEFINITIONS)  # las definiciones son JSON puro (compatibles con APIs de tool use)


async def test_search_returns_only_real_active_courses(session):
    await make_course(session, slug="ceramica-real", price_minor=15_000_000)
    await make_course(session, status="DRAFT", slug="borrador")
    await session.commit()
    r = await execute_tool(session, "search_courses", {"query": "principiantes", "max_price_cop": 200_000})
    assert [c["slug"] for c in r["courses"]] == ["ceramica-real"] and r["courses"][0]["seats_available"] == 5
    none = await execute_tool(session, "search_courses", {"query": "astrofísica cuántica"})
    assert none == {"total_matching": 0, "courses": []}  # sin resultados => lo dice; no inventa


async def test_price_filter_uses_pesos_not_cents(session):
    await make_course(session, slug="caro", price_minor=50_000_000)  # 500.000 COP
    await session.commit()
    assert (await execute_tool(session, "search_courses", {"max_price_cop": 100_000}))["courses"] == []
    assert len((await execute_tool(session, "search_courses", {"max_price_cop": 600_000}))["courses"]) == 1


async def test_details_and_availability_and_errors_as_data(session):
    c = await make_course(session, slug="detalle")
    await session.commit()
    d = await execute_tool(session, "get_course_details", {"slug": "detalle"})
    assert d["id"] == str(c.id) and d["booking_open"] is True
    a = await execute_tool(session, "check_availability", {"course_id": str(c.id)})
    assert a["seats_available"] == 5
    assert (await execute_tool(session, "get_course_details", {"slug": "no-existe"}))["error"] == "NOT_FOUND"
    assert (await execute_tool(session, "check_availability", {"course_id": "no-es-uuid"}))[
        "error"
    ] == "invalid_arguments"
    assert (await execute_tool(session, "create_booking", {"course_id": str(c.id)}))["error"] == "unknown_tool"


async def test_tools_never_change_data(session):
    c = await make_course(session)
    await make_user(session)
    await session.commit()
    for name, args in [
        ("search_courses", {}),
        ("get_course_details", {"slug": c.translations[0].slug}),
        ("check_availability", {"course_id": str(c.id)}),
    ]:
        await execute_tool(session, name, args)
    assert (await session.execute(select(func.count()).select_from(Booking))).scalar_one() == 0
