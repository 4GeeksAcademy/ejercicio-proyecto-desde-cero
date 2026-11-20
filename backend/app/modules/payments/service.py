"""Pagos: iniciar cobro, procesar webhooks (seguros e idempotentes), reembolsos y comisión."""

import uuid
from collections.abc import Mapping
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.config import get_settings
from app.core.errors import BusinessRuleError, ConflictError, ExternalServiceError, NotFoundError
from app.modules.audit import service as audit
from app.modules.auth.dependencies import Principal
from app.modules.bookings import service as bookings
from app.modules.bookings.models import BookingStatus
from app.modules.bookings.state_machine import Actor, Event
from app.modules.core_events import service as events
from app.modules.payments.commission import compute_commission
from app.modules.payments.models import AppSetting, Commission, Payment, PaymentEvent, PaymentStatus
from app.modules.payments.provider import ProviderEventType, get_provider
from app.modules.payments.schemas import (
    AdminPaymentOut,
    CommissionOut,
    CommissionSummary,
    PaymentOut,
)

log = structlog.get_logger()
P = PaymentStatus
B = BookingStatus
OPEN_STATUSES = (P.PENDING.value, P.PROCESSING.value)


class PaymentNotAllowedError(ConflictError):
    code = "BOOKING_NOT_PAYABLE"
    message = "Esta reserva no se puede pagar en su estado actual."


def _out(p: Payment) -> PaymentOut:
    return PaymentOut(
        id=p.id,
        booking_id=p.booking_id,
        status=p.status,
        amount_minor=p.amount_minor,
        currency=p.currency,
        provider=p.provider,
        checkout_url=p.checkout_url if p.status in OPEN_STATUSES else None,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


async def _audit_status(session: AsyncSession, payment: Payment, old: str, new: str) -> None:
    await audit.record(
        session,
        actor_id=None,
        action="payment.status_changed",
        resource_type="payment",
        resource_id=payment.id,
        changes={"from": old, "to": new, "provider": payment.provider},
    )


# ------------------------------------------------------------------ comisión configurable


async def get_commission_bps(session: AsyncSession) -> int:
    row = await session.get(AppSetting, "commission_bps")
    return int(row.value["bps"]) if row else get_settings().default_commission_bps


async def set_commission_bps(session: AsyncSession, principal: Principal, bps: int) -> int:
    old = await get_commission_bps(session)
    row = await session.get(AppSetting, "commission_bps")
    if row:
        row.value = {"bps": bps}
    else:
        session.add(AppSetting(key="commission_bps", value={"bps": bps}))
    await audit.record(
        session,
        actor_id=principal.user.id,
        action="settings.commission_changed",
        resource_type="setting",
        resource_id="commission_bps",
        changes={"from": old, "to": bps},
    )
    await session.commit()
    return bps


async def _accrue_commission(session: AsyncSession, payment: Payment) -> None:
    """Snapshot contable: el porcentaje vigente HOY queda fijado para esta reserva."""
    bps = await get_commission_bps(session)
    commission, net = compute_commission(payment.amount_minor, bps)
    session.add(
        Commission(
            booking_id=payment.booking_id,
            payment_id=payment.id,
            gross_minor=payment.amount_minor,
            commission_bps=bps,
            commission_minor=commission,
            net_minor=net,
            currency=payment.currency,
            status="ACCRUED",
            beneficiary=None,  # [PENDIENTE P-01] quién recibe exactamente el 20 %
        )
    )


# ------------------------------------------------------------------ iniciar pago


async def _open_payment(session: AsyncSession, booking_id: uuid.UUID) -> Payment | None:
    return (
        await session.execute(
            select(Payment).where(Payment.booking_id == booking_id, Payment.status.in_(OPEN_STATUSES))
        )
    ).scalar_one_or_none()


async def start_payment(session: AsyncSession, principal: Principal, booking_id: uuid.UUID) -> PaymentOut:
    booking = await bookings.lock_booking(session, booking_id)
    if booking.user_id != principal.user.id:
        raise NotFoundError("Reserva no encontrada.", code="BOOKING_NOT_FOUND")
    existing = await _open_payment(session, booking.id)
    if existing and existing.checkout_url:
        return _out(existing)  # reintento / doble clic: mismo pago
    if booking.status != B.PENDING_PAYMENT.value:
        raise PaymentNotAllowedError()
    if booking.expires_at and booking.expires_at <= clock.now():
        raise BusinessRuleError("El plazo de pago ha vencido.", code="PAYMENT_WINDOW_EXPIRED")

    provider_name = "none" if booking.price_minor == 0 else get_settings().payment_provider
    payment = existing or Payment(
        booking_id=booking.id,
        user_id=booking.user_id,
        amount_minor=booking.price_minor,
        currency=booking.currency,
        provider=provider_name,
        status=P.PENDING.value,
    )
    if existing is None:
        session.add(payment)
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            raise PaymentNotAllowedError() from exc

    if booking.price_minor == 0:  # curso gratuito: no hay nada que cobrar
        payment.status = P.PAID.value
        await bookings.on_payment_confirmed(session, booking.id)
        await _accrue_commission(session, payment)
        await _audit_status(session, payment, P.PENDING.value, P.PAID.value)
        await session.commit()
        await session.refresh(payment)
        return _out(payment)

    await session.commit()  # liberamos el bloqueo ANTES de llamar a un servicio externo
    payment_id = payment.id
    try:
        checkout = await get_provider().create_checkout(
            payment_id, payment.amount_minor, payment.currency, f"Reserva {booking.id}"
        )
    except Exception as exc:
        log.exception("payment_checkout_failed")
        payment = await session.get(Payment, payment_id, with_for_update=True)  # type: ignore[assignment]
        payment.status = P.FAILED.value
        await _audit_status(session, payment, P.PENDING.value, P.FAILED.value)
        await session.commit()
        raise ExternalServiceError("No pudimos iniciar el pago. Inténtalo de nuevo en unos minutos.") from exc

    booking = await bookings.lock_booking(session, booking_id)
    payment = await session.get(Payment, payment_id, with_for_update=True)  # type: ignore[assignment]
    payment.transaction_reference = checkout.reference
    payment.checkout_url = checkout.url
    payment.status = P.PROCESSING.value
    if booking.status == B.PENDING_PAYMENT.value:
        await bookings.on_payment_initiated(session, booking.id)
    await _audit_status(session, payment, P.PENDING.value, P.PROCESSING.value)
    await session.commit()
    await session.refresh(payment)
    return _out(payment)


# ------------------------------------------------------------------ webhooks


async def handle_webhook(
    session: AsyncSession, provider_name: str, headers: Mapping[str, str], raw_body: bytes
) -> dict[str, str]:
    """Orden: 1) validar firma  2) confirmar con el proveedor  3) deduplicar  4) aplicar. Todo idempotente."""
    provider = get_provider(provider_name)
    event = provider.verify_webhook(headers, raw_body)  # 401 si la firma/fecha no son válidas
    authoritative = await provider.get_status(event.reference)  # no nos fiamos solo del payload

    stmt = (
        pg_insert(PaymentEvent)
        .values(
            id=uuid.uuid4(),
            provider=provider.name,
            provider_event_id=event.event_id,
            event_type=event.type.value,
            payload=event.raw,
            signature_valid=True,
        )
        .on_conflict_do_nothing(constraint="uq_payment_events_provider_event")
        .returning(PaymentEvent.id)
    )
    event_row_id = (await session.execute(stmt)).scalar_one_or_none()
    if event_row_id is None:
        log.info("webhook_duplicate", event_name="webhook_duplicate", provider=provider.name)
        await session.rollback()
        return {"status": "duplicate"}
    pe = await session.get(PaymentEvent, event_row_id)
    assert pe is not None  # noqa: S101

    payment = (
        await session.execute(
            select(Payment)
            .where(Payment.provider == provider.name, Payment.transaction_reference == event.reference)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if payment is None:
        log.warning("webhook_unknown_reference", event_name="webhook_unknown_reference", provider=provider.name)
        pe.processed_at = clock.now()
        await session.commit()
        return {"status": "ignored"}
    pe.payment_id = payment.id

    result = "processed"
    if event.type == ProviderEventType.SUCCEEDED:
        if authoritative.status != "PAID":
            log.error("webhook_state_mismatch", event_name="webhook_state_mismatch", payment_id=str(payment.id))
            result = "ignored"
        elif (event.amount_minor, event.currency) != (payment.amount_minor, payment.currency) or (
            authoritative.amount_minor,
            authoritative.currency,
        ) != (payment.amount_minor, payment.currency):
            log.error("webhook_amount_mismatch", event_name="webhook_amount_mismatch", payment_id=str(payment.id))
            events.emit(session, "payment_amount_mismatch", "payment", payment.id, {"payment_id": str(payment.id)})
            result = "rejected"
        else:
            await _apply_paid(session, payment)
    else:
        await _apply_failed(session, payment)
    pe.processed_at = clock.now()
    await session.commit()
    return {"status": result}


async def _apply_paid(session: AsyncSession, payment: Payment) -> None:
    if payment.status in (P.PAID.value, P.REFUNDED.value):
        return  # ya aplicado: un segundo evento "pagado" no hace nada
    old = payment.status
    payment.status = P.PAID.value
    await _audit_status(session, payment, old, P.PAID.value)
    booking = await bookings.lock_booking(session, payment.booking_id)
    if booking.status in (B.PENDING_PAYMENT.value, B.PAYMENT_PROCESSING.value):
        final = await bookings.on_payment_confirmed(session, booking.id)
        await _accrue_commission(session, payment)
        events.emit(
            session,
            "payment_completed",
            "payment",
            payment.id,
            {"booking_id": str(booking.id), "booking_status": final.value},
        )
    else:
        # Pago tardío o reserva ya cerrada (RN-14): NO se confirma plaza; hay que devolver el dinero.
        log.warning(
            "late_payment", event_name="late_payment", payment_id=str(payment.id), booking_status=booking.status
        )
        events.emit(
            session,
            "payment_needs_refund",
            "payment",
            payment.id,
            {"booking_id": str(booking.id), "booking_status": booking.status, "reason": "booking_not_payable"},
        )


async def _apply_failed(session: AsyncSession, payment: Payment) -> None:
    if payment.status in (P.PAID.value, P.REFUNDED.value, P.FAILED.value, P.CANCELLED.value):
        return  # un fallo atrasado no deshace un pago ya confirmado
    old = payment.status
    payment.status = P.FAILED.value
    await _audit_status(session, payment, old, P.FAILED.value)
    booking = await bookings.lock_booking(session, payment.booking_id)
    if booking.status == B.PAYMENT_PROCESSING.value:
        await bookings.on_payment_failed(session, booking.id)  # vuelve a PENDING_PAYMENT (puede reintentar)
    events.emit(session, "payment_failed", "payment", payment.id, {"booking_id": str(booking.id)})


# ------------------------------------------------------------------ reembolso (admin)


async def refund_payment(
    session: AsyncSession, principal: Principal, payment_id: uuid.UUID, reason: str
) -> AdminPaymentOut:
    payment = (
        await session.execute(select(Payment).where(Payment.id == payment_id).with_for_update())
    ).scalar_one_or_none()
    if payment is None:
        raise NotFoundError("Pago no encontrado.", code="PAYMENT_NOT_FOUND")
    if payment.status != P.PAID.value:
        raise ConflictError("Solo se pueden reembolsar pagos confirmados.", code="REFUND_NOT_ALLOWED")
    booking = await bookings.lock_booking(session, payment.booking_id)
    # [PENDIENTE P-05] hasta definir la política: solo se reembolsa si la reserva ya está cerrada (cancelada/rechazada/caducada).
    if booking.status not in (B.CANCELLED.value, B.REJECTED.value, B.EXPIRED.value):
        raise ConflictError("Cancela o rechaza la reserva antes de reembolsar el pago.", code="REFUND_NOT_ALLOWED")
    if payment.provider != "none" and payment.transaction_reference:
        try:
            await get_provider(payment.provider).refund(payment.transaction_reference, payment.amount_minor)
        except Exception as exc:
            log.exception("refund_failed")
            raise ExternalServiceError("El proveedor no pudo procesar el reembolso.") from exc
    payment.status = P.REFUNDED.value
    await _audit_status(session, payment, P.PAID.value, P.REFUNDED.value)
    if booking.status in (B.CANCELLED.value, B.REJECTED.value):
        await bookings.apply_transition(session, booking, Event.REFUND_COMPLETED, Actor.SYSTEM, reason=reason)
    commission = (
        await session.execute(select(Commission).where(Commission.payment_id == payment.id))
    ).scalar_one_or_none()
    if commission:
        commission.status = "REVERSED"
    await audit.record(
        session,
        actor_id=principal.user.id,
        action="payment.refunded",
        resource_type="payment",
        resource_id=payment.id,
        changes={"reason": True},
    )
    events.emit(session, "payment_refunded", "payment", payment.id, {"booking_id": str(booking.id)})
    await session.commit()
    await session.refresh(payment)
    return _admin_out(payment)


# ------------------------------------------------------------------ consultas


def _admin_out(p: Payment) -> AdminPaymentOut:
    return AdminPaymentOut(**_out(p).model_dump(), user_id=p.user_id, transaction_reference=p.transaction_reference)


async def list_my_payments(
    session: AsyncSession, user_id: uuid.UUID, booking_id: uuid.UUID | None, limit: int, offset: int
) -> tuple[list[PaymentOut], int]:
    stmt = select(Payment).where(Payment.user_id == user_id)
    if booking_id:
        stmt = stmt.where(Payment.booking_id == booking_id)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(Payment.created_at.desc()).limit(limit).offset(offset))).scalars().all()
    return [_out(p) for p in rows], total


async def admin_list_payments(
    session: AsyncSession, status: str | None, limit: int, offset: int
) -> tuple[list[AdminPaymentOut], int]:
    stmt = select(Payment)
    if status:
        stmt = stmt.where(Payment.status == status)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(Payment.created_at.desc()).limit(limit).offset(offset))).scalars().all()
    return [_admin_out(p) for p in rows], total


async def admin_commissions(session: AsyncSession, limit: int, offset: int) -> CommissionSummary:
    total = (await session.execute(select(func.count()).select_from(Commission))).scalar_one()
    rows = (
        (await session.execute(select(Commission).order_by(Commission.created_at.desc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    agg = (
        await session.execute(
            select(
                Commission.currency,
                func.sum(Commission.gross_minor),
                func.sum(Commission.commission_minor),
                func.sum(Commission.net_minor),
            )
            .where(Commission.status != "REVERSED")
            .group_by(Commission.currency)
        )
    ).all()
    totals: dict[str, dict[str, int]] = {
        cur: {"gross_minor": int(g), "commission_minor": int(c), "net_minor": int(n)} for cur, g, c, n in agg
    }
    items: list[dict[str, Any]] = [
        {
            "id": c.id,
            "booking_id": c.booking_id,
            "payment_id": c.payment_id,
            "gross_minor": c.gross_minor,
            "commission_bps": c.commission_bps,
            "commission_minor": c.commission_minor,
            "net_minor": c.net_minor,
            "currency": c.currency,
            "status": c.status,
            "beneficiary": c.beneficiary,
            "created_at": c.created_at,
        }
        for c in rows
    ]
    return CommissionSummary(
        items=[CommissionOut(**i) for i in items], total=total, totals_by_currency=totals, limit=limit, offset=offset
    )
