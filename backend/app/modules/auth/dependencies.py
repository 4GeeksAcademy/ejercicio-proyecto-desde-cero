"""Dependencias FastAPI: quién eres (autenticación) y qué puedes hacer (autorización RBAC)."""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.security import constant_time_equals, decode_access_token
from app.modules.auth.models import User

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class Principal:
    user: User
    permissions: frozenset[str]

    @property
    def roles(self) -> set[str]:
        return {r.name for r in self.user.roles}

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def _check_csrf(request: Request) -> None:
    """Doble envío: la cabecera X-CSRF-Token debe coincidir con la cookie csrf_token (solo operaciones que modifican)."""
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get("X-CSRF-Token", "")
    if not cookie or not header or not constant_time_equals(cookie, header):
        raise PermissionDeniedError("Petición no válida (CSRF).", code="CSRF_FAILED")


def principal_for(user: User) -> Principal:
    perms = {p.name for role in user.roles for p in role.permissions}
    return Principal(user=user, permissions=frozenset(perms))


async def get_current_principal(request: Request, session: AsyncSession = Depends(get_session)) -> Principal:
    token = request.cookies.get(ACCESS_COOKIE)
    payload = decode_access_token(token) if token else None
    if payload is None:
        raise AuthenticationError()
    if request.method not in SAFE_METHODS:
        _check_csrf(request)
    user = await session.get(User, payload["sub"])
    if user is None or not user.is_active or user.anonymized_at:
        raise AuthenticationError()
    return principal_for(user)


async def get_optional_principal(request: Request, session: AsyncSession = Depends(get_session)) -> Principal | None:
    if not request.cookies.get(ACCESS_COOKIE):
        return None
    try:
        return await get_current_principal(request, session)
    except AuthenticationError:
        return None


def require_permission(*needed: str) -> Callable[[Principal], Principal]:
    """Uso: Depends(require_permission('course:write')). 401 si no hay sesión, 403 si falta permiso."""

    async def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        missing = [p for p in needed if not principal.can(p)]
        if missing:
            raise PermissionDeniedError()
        return principal

    return dependency  # type: ignore[return-value]
