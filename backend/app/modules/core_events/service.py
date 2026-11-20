import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.core_events.models import DomainEvent


def emit(
    session: AsyncSession, event_type: str, aggregate_type: str, aggregate_id: uuid.UUID | None, payload: dict[str, Any]
) -> None:
    """Outbox: el evento se confirma/revierte JUNTO con el cambio de negocio (misma transacción)."""
    session.add(
        DomainEvent(event_type=event_type, aggregate_type=aggregate_type, aggregate_id=aggregate_id, payload=payload)
    )
