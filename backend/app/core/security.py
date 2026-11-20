"""Primitivas de seguridad: hashing de contraseñas, JWT y tokens opacos.

- Contraseñas: argon2id (nunca texto plano, nunca reversible).
- Access token: JWT corto (15 min). El refresh token es OPACO y se guarda como hash SHA-256.
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()  # parámetros por defecto de argon2-cffi (argon2id)
# Hash de relleno para igualar tiempos cuando el usuario no existe (evita enumeración por timing).
DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(user_id: uuid.UUID, now: datetime | None = None) -> str:
    s = get_settings()
    now = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_minutes),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token, get_settings().jwt_secret, algorithms=["HS256"], options={"require": ["exp", "sub", "type"]}
        )
    except jwt.PyJWTError:
        return None
    return payload if payload.get("type") == "access" else None


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
