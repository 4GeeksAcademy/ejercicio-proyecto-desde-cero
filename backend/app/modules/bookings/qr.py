"""Token de QR de una reserva. [PENDIENTE P-08: función exacta del QR; hoy sirve para check-in].

- NO contiene datos personales: solo el id de la reserva (UUID, opaco) y una firma HMAC.
- No se almacena: se recalcula; si cambia JWT_SECRET los QR antiguos dejan de valer.
"""

import base64
import hashlib
import hmac
import uuid

from app.core.config import get_settings
from app.core.errors import ConflictError


class InvalidQrError(ConflictError):
    status_code = 422
    code = "INVALID_QR"
    message = "Código QR no válido."


def _mac(booking_id: uuid.UUID) -> str:
    key = hashlib.sha256(b"qr:" + get_settings().jwt_secret.encode()).digest()
    return base64.urlsafe_b64encode(hmac.new(key, booking_id.bytes, hashlib.sha256).digest()[:16]).decode().rstrip("=")


def make_token(booking_id: uuid.UUID) -> str:
    return f"{base64.urlsafe_b64encode(booking_id.bytes).decode().rstrip('=')}.{_mac(booking_id)}"


def parse_token(token: str) -> uuid.UUID:
    try:
        raw_id, mac = token.split(".", 1)
        booking_id = uuid.UUID(bytes=base64.urlsafe_b64decode(raw_id + "=" * (-len(raw_id) % 4)))
    except Exception as exc:
        raise InvalidQrError() from exc
    if not hmac.compare_digest(_mac(booking_id), mac):
        raise InvalidQrError()
    return booking_id
