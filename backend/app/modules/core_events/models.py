import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UUIDMixin


class DomainEvent(UUIDMixin, Base):
    """Outbox: se escribe en la MISMA transacción que el cambio de negocio; un worker lo procesa."""

    __tablename__ = "domain_events"
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(40), nullable=False)
    aggregate_id: Mapped[uuid.UUID | None] = mapped_column()
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        Index(
            "ix_domain_events_unprocessed",
            "occurred_at",
            postgresql_where=text("processed_at IS NULL AND attempts < 5"),
        ),
    )
