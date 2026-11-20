import json

import pytest
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core.telemetry import setup_telemetry, shutdown_telemetry
from tests.factories import make_course, make_user
from tests.integration.test_bookings import book


@pytest.fixture
def otel(app):
    spans = InMemorySpanExporter()
    reader = InMemoryMetricReader()
    assert setup_telemetry(app, span_processor=SimpleSpanProcessor(spans), metric_reader=reader)
    yield spans, reader
    shutdown_telemetry(app)


def metric_names(reader):
    data = reader.get_metrics_data()
    return {m.name for rm in data.resource_metrics for sm in rm.scope_metrics for m in sm.metrics} if data else set()


async def test_booking_request_produces_one_trace_across_layers(session, auth_client, otel, capsys):
    spans, reader = otel
    course = await make_course(session)
    user = await make_user(session, role="CLIENT")
    await session.commit()
    c = await auth_client(user)
    r = await book(c, course.id)
    assert r.status_code == 201

    finished = spans.get_finished_spans()
    by_name = {s.name: s for s in finished}
    http = next(s for s in finished if s.name.startswith("POST") and "bookings" in s.name)
    biz = by_name["booking.create"]
    # Mismo trace_id: la petición HTTP, la operación de negocio y las consultas SQL se pueden seguir juntas.
    assert biz.context.trace_id == http.context.trace_id
    sql = [s for s in finished if s.attributes and s.attributes.get("db.system") == "postgresql"]
    in_request = [s for s in sql if s.context.trace_id == http.context.trace_id]
    assert any(
        "FOR UPDATE" in s.attributes["db.statement"] for s in in_request
    )  # el bloqueo de cupo es visible en la traza
    # Solo la sentencia con marcadores: ningún valor de parámetro (email, ids...) viaja en la telemetría.
    assert not any(user.email in str(s.attributes) for s in sql)
    assert biz.attributes["course.id"] == str(course.id)

    # Los logs de esa petición llevan el trace_id => de un log se salta a su traza.
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    with_trace = [e for e in lines if e.get("trace_id")]
    assert with_trace and any(e["trace_id"] == format(http.context.trace_id, "032x") for e in with_trace)

    # Métrica de NEGOCIO + métricas técnicas HTTP
    names = metric_names(reader)
    assert "tallerya.booking.transitions" in names
    assert any(n.startswith("http.server") for n in names)


async def test_health_checks_are_not_traced(client, otel):
    spans, _ = otel
    await client.get("/health")
    await client.get("/ready")
    assert [s for s in spans.get_finished_spans() if "health" in s.name or "ready" in s.name] == []


async def test_telemetry_is_off_by_default(app):
    from app.core.telemetry import setup_telemetry as st

    assert st(app) is False
