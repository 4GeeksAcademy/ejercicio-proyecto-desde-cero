"""Endpoints de administración transversales (usuarios y administradores)."""

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import ConflictError, NotFoundError
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
