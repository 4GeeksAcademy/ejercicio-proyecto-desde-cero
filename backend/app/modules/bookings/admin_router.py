import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.dependencies import Principal, require_permission
from app.modules.bookings import service
from app.modules.bookings.schemas import AdminBookingOut, AdminBookingPage, ReasonRequest
from app.modules.bookings.state_machine import Event

router = APIRouter(prefix="/admin", tags=["admin-bookings"])
Approver = Depends(require_permission("booking:approve"))


@router.get("/bookings", response_model=AdminBookingPage, summary="Reservas de todos los clientes")
async def list_bookings(
    course_id: uuid.UUID | None = None,
    status: Literal[
        "PENDING_PAYMENT",
        "PAYMENT_PROCESSING",
        "PAID",
        "PENDING_APPROVAL",
        "CONFIRMED",
        "REJECTED",
        "CANCELLED",
        "EXPIRED",
        "REFUNDED",
    ]
    | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: Principal = Depends(require_permission("booking:read_all")),
    session: AsyncSession = Depends(get_session),
) -> AdminBookingPage:
    items, total = await service.admin_list(session, course_id=course_id, status=status, limit=limit, offset=offset)
    return AdminBookingPage(items=items, total=total, limit=limit, offset=offset)


@router.post("/bookings/{booking_id}/approve", response_model=AdminBookingOut, summary="Aceptar al participante")
async def approve(
    booking_id: uuid.UUID, principal: Principal = Approver, session: AsyncSession = Depends(get_session)
) -> AdminBookingOut:
    return await service.admin_decide(session, principal, booking_id, Event.APPROVED, None)


@router.post("/bookings/{booking_id}/reject", response_model=AdminBookingOut, summary="Rechazar (motivo obligatorio)")
async def reject(
    booking_id: uuid.UUID,
    body: ReasonRequest,
    principal: Principal = Approver,
    session: AsyncSession = Depends(get_session),
) -> AdminBookingOut:
    return await service.admin_decide(session, principal, booking_id, Event.REJECTED, body.reason)


@router.post(
    "/bookings/{booking_id}/cancel", response_model=AdminBookingOut, summary="Cancelar (admin, motivo obligatorio)"
)
async def admin_cancel(
    booking_id: uuid.UUID,
    body: ReasonRequest,
    principal: Principal = Depends(require_permission("booking:cancel_any")),
    session: AsyncSession = Depends(get_session),
) -> AdminBookingOut:
    return await service.admin_decide(session, principal, booking_id, Event.CANCELLED, body.reason)


@router.post("/courses/{course_id}/cancel", summary="Cancelar un curso y todas sus reservas")
async def cancel_course(
    course_id: uuid.UUID,
    body: ReasonRequest,
    principal: Principal = Depends(require_permission("course:write", "booking:cancel_any")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    return {"bookings_cancelled": await service.cancel_course(session, course_id, principal, body.reason)}


class CheckInRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class CheckInOut(BaseModel):
    first_time: bool
    booking: AdminBookingOut


@router.post("/checkin", response_model=CheckInOut, summary="Registrar asistencia escaneando el QR")
async def checkin(
    body: CheckInRequest, principal: Principal = Approver, session: AsyncSession = Depends(get_session)
) -> CheckInOut:
    booking, first = await service.check_in(session, principal, body.token)
    return CheckInOut(first_time=first, booking=booking)
