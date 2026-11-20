import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import NotFoundError
from app.core.rate_limit import rate_limit
from app.modules.auth.dependencies import Principal, require_permission
from app.modules.payments import service
from app.modules.payments.provider import FakePaymentProvider, ProviderEventType, get_provider
from app.modules.payments.schemas import (
    AdminPaymentOut,
    AdminPaymentPage,
    CommissionSettings,
    CommissionSummary,
    PaymentOut,
    PaymentPage,
    RefundRequest,
)

router = APIRouter(tags=["payments"])
_pay_limit = rate_limit("pay", limit=15, window_seconds=60)


@router.post(
    "/bookings/{booking_id}/pay",
    response_model=PaymentOut,
    dependencies=[Depends(_pay_limit)],
    summary="Iniciar el pago de una reserva",
)
async def pay(
    booking_id: uuid.UUID,
    principal: Principal = Depends(require_permission("booking:create")),
    session: AsyncSession = Depends(get_session),
) -> PaymentOut:
    return await service.start_payment(session, principal, booking_id)


@router.get("/payments", response_model=PaymentPage, summary="Mis pagos")
async def my_payments(
    booking_id: uuid.UUID | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission("payment:read_own")),
    session: AsyncSession = Depends(get_session),
) -> PaymentPage:
    items, total = await service.list_my_payments(session, principal.user.id, booking_id, limit, offset)
    return PaymentPage(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/payments/webhooks/{provider}",
    summary="Webhook del proveedor de pagos (firma obligatoria)",
    include_in_schema=True,
)
async def webhook(provider: str, request: Request, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    raw = await request.body()
    if len(raw) > 64_000:
        raise NotFoundError("Not found")
    return await service.handle_webhook(session, provider, {k.lower(): v for k, v in request.headers.items()}, raw)


# --- Solo desarrollo/tests: simula que el usuario pagó (o falló) en la pasarela --------------------------------
dev_router = APIRouter(prefix="/dev", tags=["dev-only"])


@dev_router.post("/payments/{reference}/simulate")
async def simulate(
    reference: str, outcome: Literal["success", "failure"] = "success", session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    provider = get_provider()
    if not isinstance(provider, FakePaymentProvider) or reference not in provider.ledger:
        raise NotFoundError("Referencia desconocida.")
    kind = ProviderEventType.SUCCEEDED if outcome == "success" else ProviderEventType.FAILED
    body, headers = provider.build_webhook(kind, reference)
    return await service.handle_webhook(session, provider.name, headers, body)


def dev_enabled() -> bool:
    return get_settings().app_env in ("development", "testing")


# --- Administración -----------------------------------------------------------------------------------------
admin_router = APIRouter(prefix="/admin", tags=["admin-payments"])


@admin_router.get("/payments", response_model=AdminPaymentPage)
async def admin_payments(
    status: Literal["PENDING", "PROCESSING", "PAID", "FAILED", "CANCELLED", "REFUNDED"] | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: Principal = Depends(require_permission("payment:read_all")),
    session: AsyncSession = Depends(get_session),
) -> AdminPaymentPage:
    items, total = await service.admin_list_payments(session, status, limit, offset)
    return AdminPaymentPage(items=items, total=total, limit=limit, offset=offset)


@admin_router.post(
    "/payments/{payment_id}/refund", response_model=AdminPaymentOut, summary="Reembolsar un pago (reserva ya cerrada)"
)
async def refund(
    payment_id: uuid.UUID,
    body: RefundRequest,
    principal: Principal = Depends(require_permission("payment:refund")),
    session: AsyncSession = Depends(get_session),
) -> AdminPaymentOut:
    return await service.refund_payment(session, principal, payment_id, body.reason)


@admin_router.get("/commissions", response_model=CommissionSummary)
async def commissions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: Principal = Depends(require_permission("commission:read")),
    session: AsyncSession = Depends(get_session),
) -> CommissionSummary:
    return await service.admin_commissions(session, limit, offset)


@admin_router.get("/settings/commission", response_model=CommissionSettings)
async def get_commission(
    _: Principal = Depends(require_permission("commission:read")), session: AsyncSession = Depends(get_session)
) -> CommissionSettings:
    return CommissionSettings(commission_bps=await service.get_commission_bps(session))


@admin_router.put(
    "/settings/commission", response_model=CommissionSettings, summary="Cambiar el % de comisión (solo propietario)"
)
async def set_commission(
    body: CommissionSettings,
    principal: Principal = Depends(require_permission("settings:write")),
    session: AsyncSession = Depends(get_session),
) -> CommissionSettings:
    return CommissionSettings(commission_bps=await service.set_commission_bps(session, principal, body.commission_bps))
