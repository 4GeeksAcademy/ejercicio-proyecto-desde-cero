import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PaymentOut(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    status: str
    amount_minor: int
    currency: str
    provider: str
    checkout_url: str | None = Field(default=None, description="Solo mientras el pago está pendiente")
    created_at: datetime
    updated_at: datetime


class PaymentPage(BaseModel):
    items: list[PaymentOut]
    total: int
    limit: int
    offset: int


class AdminPaymentOut(PaymentOut):
    user_id: uuid.UUID
    transaction_reference: str | None


class AdminPaymentPage(BaseModel):
    items: list[AdminPaymentOut]
    total: int
    limit: int
    offset: int


class CommissionOut(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    payment_id: uuid.UUID
    gross_minor: int
    commission_bps: int
    commission_minor: int
    net_minor: int
    currency: str
    status: str
    beneficiary: str | None
    created_at: datetime


class CommissionSummary(BaseModel):
    items: list[CommissionOut]
    total: int
    totals_by_currency: dict[str, dict[str, int]]
    limit: int
    offset: int


class CommissionSettings(BaseModel):
    commission_bps: int = Field(ge=0, le=10_000, description="2000 = 20 %")


class RefundRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=300)
