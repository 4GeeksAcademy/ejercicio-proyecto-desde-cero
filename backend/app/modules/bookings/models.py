import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    PrimaryKeyConstraint,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDMixin
from app.core.types import check_in


class BookingStatus(StrEnum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAYMENT_PROCESSING = "PAYMENT_PROCESSING"
    PAID = "PAID"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    REFUNDED = "REFUNDED"


# Estados que OCUPAN una plaza del curso.
SEAT_HOLDING_STATUSES = (
    BookingStatus.PENDING_PAYMENT,
    BookingStatus.PAYMENT_PROCESSING,
    BookingStatus.PAID,
    BookingStatus.PENDING_APPROVAL,
    BookingStatus.CONFIRMED,
)
_HOLDING_SQL = ", ".join(f"'{s.value}'" for s in SEAT_HOLDING_STATUSES)


class Booking(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "bookings"
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_minor: Mapped[int] = mapped_column(nullable=False)  # snapshot del precio al reservar
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # asistencia (QR) [PENDIENTE P-08]

    __table_args__ = (
        check_in("status", BookingStatus, "status_valid"),
        CheckConstraint("price_minor >= 0", name="price_non_negative"),
        # CINTURÓN DE SEGURIDAD: una persona no puede tener 2 reservas que ocupen plaza en el mismo curso.
        Index(
            "uq_bookings_one_active_per_user_course",
            "course_id",
            "user_id",
            unique=True,
            postgresql_where=text(f"status IN ({_HOLDING_SQL})"),
        ),
        Index("ix_bookings_course_id_status", "course_id", "status"),
        Index("ix_bookings_user_id_created_at", "user_id", "created_at"),
        Index(
            "ix_bookings_pending_expiry",
            "expires_at",
            postgresql_where=text("status = 'PENDING_PAYMENT'"),
        ),
    )


class BookingStatusHistory(UUIDMixin, Base):
    __tablename__ = "booking_status_history"
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    event: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(10), nullable=False)  # USER | ADMIN | SYSTEM
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False, unique=True)  # orden estricto
    __table_args__ = (
        check_in("to_status", BookingStatus, "to_status_valid"),
        CheckConstraint("actor_type IN ('USER', 'ADMIN', 'SYSTEM')", name="actor_type_valid"),
    )


class IdempotencyKey(Base):
    """Guarda la respuesta de una operación para que reintentarla no la repita."""

    __tablename__ = "idempotency_keys"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    scope: Mapped[str] = mapped_column(String(60))
    key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (PrimaryKeyConstraint("user_id", "scope", "key"),)
