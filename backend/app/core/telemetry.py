"""Observabilidad (OpenTelemetry): trazas, métricas y correlación con los logs.

- Desactivada por defecto. Se activa con OTEL_ENABLED=true; si además hay OTEL_EXPORTER_OTLP_ENDPOINT,
  envía los datos al Collector (ver observability/).
- TELEMETRÍA TÉCNICA (latencia, errores, spans) ≠ ANALÍTICA DE NEGOCIO (eso va por el outbox/pipeline)
  ≠ AUDITORÍA (tabla audit_logs).
"""

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, Status, StatusCode
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.core.config import get_settings

_sql_listeners: list[tuple[Engine, str, Callable[..., Any]]] = []
_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None


def tracer() -> trace.Tracer:
    return (_tracer_provider or trace.get_tracer_provider()).get_tracer("tallerya")


def meter() -> metrics.Meter:
    return (_meter_provider or metrics.get_meter_provider()).get_meter("tallerya")


class _Counters:
    """Contadores de NEGOCIO expuestos como métricas (p. ej. bookings_created)."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    def add(self, name: str, value: int = 1, **attrs: str) -> None:
        c = self._cache.get(name)
        if c is None or self._cache.get("_provider") is not _meter_provider:
            self._cache.clear()
            self._cache["_provider"] = _meter_provider
            c = self._cache[name] = meter().create_counter(name)
        c.add(value, attributes=attrs)


counters = _Counters()


def current_trace_ids() -> tuple[str, str] | None:
    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid:
        return None
    return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")


def setup_telemetry(
    app: FastAPI,
    *,
    span_processor: SpanProcessor | None = None,
    metric_reader: MetricReader | None = None,
) -> bool:
    """Instrumenta la app. Los parámetros permiten inyectar exportadores en memoria (tests)."""
    global _tracer_provider, _meter_provider
    s = get_settings()
    if not (s.otel_enabled or span_processor or metric_reader):
        return False
    resource = Resource.create({"service.name": s.service_name, "deployment.environment": s.app_env})
    _tracer_provider = TracerProvider(resource=resource)
    readers: list[MetricReader] = []
    if metric_reader:
        readers.append(metric_reader)
    if s.otel_exporter_otlp_endpoint:
        base = s.otel_exporter_otlp_endpoint.rstrip("/")
        _tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{base}/v1/traces")))
        readers.append(PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=f"{base}/v1/metrics")))
    if span_processor:
        _tracer_provider.add_span_processor(span_processor)
    _meter_provider = MeterProvider(resource=resource, metric_readers=readers)

    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=_tracer_provider, meter_provider=_meter_provider, excluded_urls="health,ready"
    )
    from app.core.db import get_engine

    _instrument_sql(get_engine().sync_engine, _tracer_provider)
    return True


def _instrument_sql(engine: Engine, provider: TracerProvider) -> None:
    """Un span por consulta SQL (hijo de la petición actual). NO se guardan los valores de los parámetros.

    (El paquete oficial de instrumentación aún no soporta SQLAlchemy 2.1, por eso usamos los eventos del motor.)
    """
    sql_tracer = provider.get_tracer("tallerya.sql")

    def before(conn: Any, cursor: Any, statement: str, params: Any, context: Any, executemany: bool) -> None:
        if statement.strip() == "SELECT 1":  # healthcheck/ping: ruido sin valor
            return
        op = statement.lstrip().split(" ", 1)[0].upper()[:12] or "SQL"
        context._otel_span = sql_tracer.start_span(
            f"db.{op.lower()}",
            kind=SpanKind.CLIENT,
            attributes={"db.system": "postgresql", "db.operation": op, "db.statement": statement[:500]},
        )

    def after(conn: Any, cursor: Any, statement: str, params: Any, context: Any, executemany: bool) -> None:
        span = getattr(context, "_otel_span", None)
        if span is not None:
            span.end()

    def on_error(exc_context: Any) -> None:
        span = getattr(exc_context.execution_context, "_otel_span", None)
        if span is not None:
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(exc_context.original_exception)
            span.end()

    for name, fn in (("before_cursor_execute", before), ("after_cursor_execute", after), ("handle_error", on_error)):
        event.listen(engine, name, fn)
        _sql_listeners.append((engine, name, fn))


def shutdown_telemetry(app: FastAPI | None = None) -> None:
    global _tracer_provider, _meter_provider
    for engine, name, fn in _sql_listeners:
        event.remove(engine, name, fn)
    _sql_listeners.clear()
    if app is not None:
        FastAPIInstrumentor.uninstrument_app(app)
    _tracer_provider = None
    _meter_provider = None
