import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

NextAction = Literal["pay", "wait_payment", "wait_approval", "attend", "none"]


class CreateBookingRequest(BaseModel):
    course_id: uuid.UUID


class CancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class BookingCourse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    starts_at: datetime
    ends_at: datetime
    timezone: str
    address: str


class HistoryItem(BaseModel):
    from_status: str | None
    to_status: str
    event: str
    at: datetime


class BookingOut(BaseModel):
    id: uuid.UUID
    status: str
    expires_at: datetime | None
    price_minor: int
    currency: str
    created_at: datetime
    course: BookingCourse
    next_action: NextAction = Field(description="Qué debe hacer ahora el cliente")
    can_cancel: bool
    history: list[HistoryItem] | None = None


class BookingPage(BaseModel):
    items: list[BookingOut]
    total: int
    limit: int
    offset: int


class AdminBookingOut(BookingOut):
    user_id: uuid.UUID
    user_name: str
    user_email: str


class AdminBookingPage(BaseModel):
    items: list[AdminBookingOut]
    total: int
    limit: int
    offset: int
