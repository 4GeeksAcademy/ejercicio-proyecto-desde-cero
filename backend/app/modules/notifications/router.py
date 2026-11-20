import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.dependencies import Principal, require_permission
from app.modules.notifications import service

router = APIRouter(prefix="/notifications", tags=["notifications"])
Reader = Depends(require_permission("notification:read_own"))


class NotificationOut(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    body: str
    booking_id: uuid.UUID | None = None
    read: bool
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    total: int
    unread: int


class Preferences(BaseModel):
    email_enabled: bool | None = None
    whatsapp_enabled: bool | None = None


@router.get("", response_model=NotificationPage, summary="Mis notificaciones")
async def mine(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: Principal = Reader,
    session: AsyncSession = Depends(get_session),
) -> NotificationPage:
    rows, total, unread = await service.list_notifications(session, principal.user.id, limit, offset)
    items = [
        NotificationOut(
            id=n.id,
            kind=n.payload.get("kind", n.type),
            title=n.payload["title"],
            body=n.payload["body"],
            booking_id=n.payload.get("booking_id"),
            read=n.read_at is not None,
            created_at=n.created_at,
        )
        for n in rows
    ]
    return NotificationPage(items=items, total=total, unread=unread)


@router.patch("/{notification_id}/read", status_code=204)
async def read(
    notification_id: uuid.UUID, principal: Principal = Reader, session: AsyncSession = Depends(get_session)
) -> Response:
    await service.mark_read(session, principal.user.id, notification_id)
    return Response(status_code=204)


@router.get("/preferences", response_model=Preferences)
async def get_prefs(principal: Principal = Reader, session: AsyncSession = Depends(get_session)) -> Preferences:
    p = await service.get_preferences(session, principal.user.id)
    await session.commit()
    return Preferences(email_enabled=p.email_enabled, whatsapp_enabled=p.whatsapp_enabled)


@router.put("/preferences", response_model=Preferences)
async def put_prefs(
    body: Preferences, principal: Principal = Reader, session: AsyncSession = Depends(get_session)
) -> Preferences:
    p = await service.update_preferences(session, principal.user.id, body.email_enabled, body.whatsapp_enabled)
    return Preferences(email_enabled=p.email_enabled, whatsapp_enabled=p.whatsapp_enabled)
