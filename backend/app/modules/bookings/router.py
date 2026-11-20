import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.rate_limit import rate_limit
from app.modules.auth.dependencies import Principal, require_permission
from app.modules.bookings import service
from app.modules.bookings.schemas import BookingOut, BookingPage, CancelRequest, CreateBookingRequest

router = APIRouter(prefix="/bookings", tags=["bookings"])
Locale = Literal["es", "en"]
_booking_limit = rate_limit("booking", limit=lambda: get_settings().booking_rate_limit_per_minute, window_seconds=60)


@router.post(
    "",
    response_model=BookingOut,
    status_code=201,
    dependencies=[Depends(_booking_limit)],
    summary="Reservar una plaza (1 persona)",
    responses={
        200: {"description": "Petición repetida con la misma Idempotency-Key: devuelve la reserva original"},
        409: {"description": "COURSE_FULL / ALREADY_BOOKED"},
        422: {"description": "Regla de negocio: curso inactivo/cancelado/finalizado o faltan <24 h"},
    },
)
async def create_booking(
    body: CreateBookingRequest,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", min_length=8, max_length=100)] = None,
    locale: Locale = "es",
    principal: Principal = Depends(require_permission("booking:create")),
    session: AsyncSession = Depends(get_session),
) -> BookingOut:
    out, created = await service.create_booking(session, principal, body.course_id, idempotency_key, locale)
    if not created:
        response.status_code = 200
    return out


@router.get("", response_model=BookingPage, summary="Mis reservas")
async def my_bookings(
    status: str | None = Query(None, max_length=20),
    locale: Locale = "es",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("booking:read_own")),
    session: AsyncSession = Depends(get_session),
) -> BookingPage:
    items, total = await service.list_my_bookings(session, principal.user.id, status, limit, offset, locale)
    return BookingPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{booking_id}", response_model=BookingOut, summary="Detalle de mi reserva con historial")
async def my_booking(
    booking_id: uuid.UUID,
    locale: Locale = "es",
    principal: Principal = Depends(require_permission("booking:read_own")),
    session: AsyncSession = Depends(get_session),
) -> BookingOut:
    return await service.get_my_booking(session, principal.user.id, booking_id, locale)


@router.post("/{booking_id}/cancel", response_model=BookingOut, summary="Cancelar mi reserva (solo si faltan >24 h)")
async def cancel(
    booking_id: uuid.UUID,
    body: CancelRequest | None = None,
    locale: Locale = "es",
    principal: Principal = Depends(require_permission("booking:cancel_own")),
    session: AsyncSession = Depends(get_session),
) -> BookingOut:
    return await service.cancel_my_booking(session, principal, booking_id, body.reason if body else None, locale)
