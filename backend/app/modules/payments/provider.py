"""Puerto de pagos: el dominio de reservas NO conoce a ningún proveedor concreto (ADR-0006).

Para añadir Wompi/Mercado Pago/PayU/... basta con implementar `PaymentProvider` y registrarlo.
Nunca pasan por aquí datos de tarjeta: el cobro ocurre en la página/widget alojado por el proveedor.
"""

import hashlib
import hmac
import json
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.core.config import get_settings
from app.core.errors import AppError


class InvalidWebhookError(AppError):
    status_code = 401
    code = "INVALID_WEBHOOK_SIGNATURE"
    message = "Firma de webhook no válida."


class ProviderEventType(StrEnum):
    SUCCEEDED = "payment.succeeded"
    FAILED = "payment.failed"


@dataclass(frozen=True)
class Checkout:
    reference: str
    url: str


@dataclass(frozen=True)
class WebhookEvent:
    event_id: str
    type: ProviderEventType
    reference: str
    amount_minor: int
    currency: str
    raw: dict[str, object]


@dataclass(frozen=True)
class ProviderStatus:
    status: str  # "PAID" | "FAILED" | "PENDING"
    amount_minor: int
    currency: str


class PaymentProvider(Protocol):
    name: str

    async def create_checkout(
        self, payment_id: uuid.UUID, amount_minor: int, currency: str, description: str
    ) -> Checkout: ...

    def verify_webhook(self, headers: Mapping[str, str], raw_body: bytes) -> WebhookEvent: ...

    async def get_status(self, reference: str) -> ProviderStatus: ...

    async def refund(self, reference: str, amount_minor: int) -> str: ...


def sign(secret: str, timestamp: str, body: bytes) -> str:
    return hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()


class FakePaymentProvider:
    """Proveedor SIMULADO para desarrollo y tests. Firma sus webhooks igual que lo haría uno real (HMAC-SHA256)."""

    name = "fake"
    # estado "en el proveedor" (en memoria): reference -> ProviderStatus
    ledger: dict[str, ProviderStatus] = {}
    refunds: list[tuple[str, int]] = []

    async def create_checkout(
        self, payment_id: uuid.UUID, amount_minor: int, currency: str, description: str
    ) -> Checkout:
        reference = f"fake_{uuid.uuid4().hex[:16]}"
        self.ledger[reference] = ProviderStatus("PENDING", amount_minor, currency)
        return Checkout(reference=reference, url=f"{get_settings().frontend_url}/pay/fake/{reference}")

    def verify_webhook(self, headers: Mapping[str, str], raw_body: bytes) -> WebhookEvent:
        s = get_settings()
        ts, sig = headers.get("x-timestamp", ""), headers.get("x-signature", "")
        if not ts.isdigit() or not sig:
            raise InvalidWebhookError()
        if abs(time.time() - int(ts)) > s.webhook_tolerance_seconds:  # anti-replay
            raise InvalidWebhookError("Webhook caducado.")
        expected = sign(s.payment_webhook_secret, ts, raw_body)
        if not hmac.compare_digest(expected, sig.removeprefix("sha256=")):
            raise InvalidWebhookError()
        try:
            data = json.loads(raw_body)
            return WebhookEvent(
                event_id=str(data["event_id"]),
                type=ProviderEventType(data["type"]),
                reference=str(data["reference"]),
                amount_minor=int(data["amount_minor"]),
                currency=str(data["currency"]),
                raw=data,
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise InvalidWebhookError("Webhook mal formado.") from exc

    async def get_status(self, reference: str) -> ProviderStatus:
        return self.ledger.get(reference, ProviderStatus("PENDING", 0, "COP"))

    async def refund(self, reference: str, amount_minor: int) -> str:
        self.refunds.append((reference, amount_minor))
        return f"refund_{uuid.uuid4().hex[:12]}"

    # --- utilidades de simulación (solo dev/tests) ---
    def build_webhook(
        self, event_type: ProviderEventType, reference: str, event_id: str | None = None
    ) -> tuple[bytes, dict[str, str]]:
        st = self.ledger[reference]
        if event_type == ProviderEventType.SUCCEEDED:
            self.ledger[reference] = ProviderStatus("PAID", st.amount_minor, st.currency)
        else:
            self.ledger[reference] = ProviderStatus("FAILED", st.amount_minor, st.currency)
        body = json.dumps(
            {
                "event_id": event_id or uuid.uuid4().hex,
                "type": event_type.value,
                "reference": reference,
                "amount_minor": st.amount_minor,
                "currency": st.currency,
            }
        ).encode()
        ts = str(int(time.time()))
        return body, {
            "x-timestamp": ts,
            "x-signature": "sha256=" + sign(get_settings().payment_webhook_secret, ts, body),
        }


_providers: dict[str, PaymentProvider] = {"fake": FakePaymentProvider()}


def get_provider(name: str | None = None) -> PaymentProvider:
    key = name or get_settings().payment_provider
    try:
        return _providers[key]
    except KeyError as exc:
        raise AppError(f"Proveedor de pagos desconocido: {key}", code="UNKNOWN_PROVIDER") from exc
