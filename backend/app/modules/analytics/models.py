import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, PrimaryKeyConstraint, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

SCHEMA = "analytics"  # datos ANALÍTICOS separados de los operativos (mismo PostgreSQL, otro esquema)


class AnalyticsEvent(Base):
    """Hecho ya validado y normalizado. PK = id del evento de dominio => reprocesar nunca duplica."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_analytics_events_type_day", "event_type", "day"), {"schema": SCHEMA})
    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)  # día en hora de Bogotá
    course_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"))
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyCourseMetrics(Base):
    __tablename__ = "daily_course_metrics"
    __table_args__ = (PrimaryKeyConstraint("day", "course_id"), {"schema": SCHEMA})
    day: Mapped[date] = mapped_column(Date)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    course_views: Mapped[int] = mapped_column(nullable=False, server_default="0")
    bookings_created: Mapped[int] = mapped_column(nullable=False, server_default="0")
    bookings_confirmed: Mapped[int] = mapped_column(nullable=False, server_default="0")
    bookings_cancelled: Mapped[int] = mapped_column(nullable=False, server_default="0")
    bookings_expired: Mapped[int] = mapped_column(nullable=False, server_default="0")
    payments_completed: Mapped[int] = mapped_column(nullable=False, server_default="0")
    payments_failed: Mapped[int] = mapped_column(nullable=False, server_default="0")
