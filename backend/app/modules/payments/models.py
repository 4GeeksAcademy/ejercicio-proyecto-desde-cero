import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDMixin
from app.core.types import check_in


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class CommissionStatus(StrEnum):
    ACCRUED = "ACCRUED"
    SETTLED = "SETTLED"
    REVERSED = "REVERSED"


class Payment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    amount_minor: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="PENDING")
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    transaction_reference: Mapped[str | None] = mapped_column(String(120))
    checkout_url: Mapped[str | None] = mapped_column(String(1000))
    __table_args__ = (
        check_in("status", PaymentStatus, "status_valid"),
        CheckConstraint("amount_minor >= 0", name="amount_non_negative"),
        UniqueConstraint("provider", "transaction_reference", name="uq_payments_provider_reference"),
        # Un booking solo puede tener UN pago "vivo" a la vez.
        Index(
            "uq_payments_one_open_per_booking",
            "booking_id",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'PROCESSING', 'PAID')"),
        ),
    )


class PaymentEvent(UUIDMixin, Base):
    """Cada webhook recibido. UNIQUE(provider, provider_event_id) => idempotencia."""

    __tablename__ = "payment_events"
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"), index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("provider", "provider_event_id", name="uq_payment_events_provider_event"),)


class Commission(UUIDMixin, TimestampMixin, Base):
    """Snapshot contable de la comisión. No se recalcula si cambia el porcentaje después."""

    __tablename__ = "commissions"
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="RESTRICT"), unique=True)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id", ondelete="RESTRICT"), unique=True)
    gross_minor: Mapped[int] = mapped_column(nullable=False)
    commission_bps: Mapped[int] = mapped_column(nullable=False)  # 2000 = 20 %
    commission_minor: Mapped[int] = mapped_column(nullable=False)
    net_minor: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="ACCRUED")
    beneficiary: Mapped[str | None] = mapped_column(String(80))  # [PENDIENTE P-01]
    __table_args__ = (
        check_in("status", CommissionStatus, "status_valid"),
        CheckConstraint("commission_bps BETWEEN 0 AND 10000", name="bps_range"),
        CheckConstraint("gross_minor >= 0 AND commission_minor >= 0 AND net_minor >= 0", name="non_negative"),
        CheckConstraint("commission_minor + net_minor = gross_minor", name="sums_to_gross"),
    )


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
