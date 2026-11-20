"""Endpoints de administración transversales (usuarios y administradores)."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import ConflictError, NotFoundError
from app.modules.admin import insights
from app.modules.audit import service as audit
from app.modules.auth.dependencies import Principal, require_permission
from app.modules.auth.models import Profile, Role, User
from app.modules.auth.service import get_user_by_email

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    roles: list[str]
    is_active: bool


class GrantAdminRequest(BaseModel):
    email: EmailStr


class Page(BaseModel):
    items: list[AdminUserOut]
    total: int
    limit: int
    offset: int


def _out(u: User) -> AdminUserOut:
    return AdminUserOut(
        id=u.id,
        email=u.email,
        full_name=u.profile.full_name,
        phone=u.profile.phone,
        roles=sorted(r.name for r in u.roles),
        is_active=u.is_active,
    )


@router.get("/users", response_model=Page, summary="Listar usuarios")
async def list_users(
    q: str | None = Query(None, max_length=100, description="Busca por nombre o correo"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: Principal = Depends(require_permission("user:read_all")),
    session: AsyncSession = Depends(get_session),
) -> Page:
    stmt = select(User).join(Profile, Profile.user_id == User.id).where(User.anonymized_at.is_(None))
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(User.email).like(like) | func.lower(Profile.full_name).like(like))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(User.created_at.desc()).limit(limit).offset(offset))).scalars().all()
    return Page(items=[_out(u) for u in rows], total=total, limit=limit, offset=offset)


async def _admin_role(session: AsyncSession) -> Role:
    return (await session.execute(select(Role).where(Role.name == "ADMIN"))).scalar_one()


@router.post("/admins", response_model=AdminUserOut, status_code=201, summary="Dar rol ADMIN (solo propietario)")
async def grant_admin(
    body: GrantAdminRequest,
    principal: Principal = Depends(require_permission("admin:manage")),
    session: AsyncSession = Depends(get_session),
) -> AdminUserOut:
    user = await get_user_by_email(session, body.email)
    if user is None or user.anonymized_at:
        raise NotFoundError("Usuario no encontrado.")
    role = await _admin_role(session)
    if role in user.roles:
        raise ConflictError("El usuario ya es administrador.", code="ALREADY_ADMIN")
    user.roles = [*user.roles, role]
    await audit.record(
        session,
        actor_id=principal.user.id,
        action="permission.admin_granted",
        resource_type="user",
        resource_id=user.id,
    )
    await session.commit()
    return _out(user)


@router.delete("/admins/{user_id}", status_code=204, summary="Quitar rol ADMIN (solo propietario)")
async def revoke_admin(
    user_id: uuid.UUID,
    principal: Principal = Depends(require_permission("admin:manage")),
    session: AsyncSession = Depends(get_session),
) -> None:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError("Usuario no encontrado.")
    role = await _admin_role(session)
    if role not in user.roles:
        raise NotFoundError("El usuario no es administrador.")
    user.roles = [r for r in user.roles if r.id != role.id]
    await audit.record(
        session,
        actor_id=principal.user.id,
        action="permission.admin_revoked",
        resource_type="user",
        resource_id=user.id,
    )
    await session.commit()


class AuditOut(BaseModel):
    id: int
    actor_user_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    changes: dict[str, Any] | None
    request_id: str | None
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditOut]
    total: int
    limit: int
    offset: int


@router.get("/audit-logs", response_model=AuditPage, summary="Registro de auditoría (solo propietario)")
async def audit_logs(
    action: str | None = Query(None, max_length=60),
    resource_type: str | None = Query(None, max_length=40),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: Principal = Depends(require_permission("audit:read")),
    session: AsyncSession = Depends(get_session),
) -> AuditPage:
    rows, total = await insights.list_audit(
        session, action=action, resource_type=resource_type, limit=limit, offset=offset
    )
    return AuditPage(
        items=[AuditOut.model_validate(r, from_attributes=True) for r in rows], total=total, limit=limit, offset=offset
    )


@router.get("/metrics", summary="Métricas de negocio para el dashboard")
async def metrics(
    principal: Principal = Depends(require_permission("metrics:read_business")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    return await insights.business_metrics(session, include_money=principal.can("commission:read"))
