"""Logs estructurados (JSON) con contexto de petición y redacción de secretos."""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

from app.core.config import get_settings

SENSITIVE_KEYS = {
    "password",
    "new_password",
    "current_password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "secret",
    "api_key",
    "card_number",
    "cvv",
    "jwt_secret",
    "signature",
}


def redact_sensitive(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    for key in list(event_dict):
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def add_trace_context(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Añade trace_id/span_id al log para saltar de un log a su traza completa."""
    from app.core.telemetry import current_trace_ids

    ids = current_trace_ids()
    if ids:
        event_dict["trace_id"], event_dict["span_id"] = ids
    return event_dict


def add_service_context(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    s = get_settings()
    event_dict.setdefault("service", s.service_name)
    event_dict.setdefault("environment", s.app_env)
    return event_dict


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level, force=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            add_service_context,
            add_trace_context,
            redact_sensitive,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=False,
    )
