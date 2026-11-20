"""Auditoría: quién hizo qué sobre qué recurso y cuándo. NO es telemetría (se guarda en BD, solo inserción)."""

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog


async def record(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | uuid.UUID | None = None,
    changes: dict[str, Any] | None = None,
) -> None:
    """Se añade a la sesión actual: se confirma (o revierte) junto con la operación auditada."""
    session.add(
        AuditLog(
            actor_user_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            changes=changes,
            request_id=structlog.contextvars.get_contextvars().get("request_id"),
        )
    )
