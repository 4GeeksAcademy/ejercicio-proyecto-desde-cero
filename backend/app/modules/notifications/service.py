import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.errors import NotFoundError
from app.core.mail import Mail, Mailer
from app.modules.auth.models import User
from app.modules.notifications.models import Notification, NotificationPreference
from app.modules.notifications.templates import render

log = structlog.get_logger()
MAX_ATTEMPTS = 5


async def notify(
    session: AsyncSession,
    user: User,
    kind: str,
    data: dict[str, Any],
    *,
    dedupe_key: str | None = None,
    email: bool = True,
) -> None:
    """Crea la notificación in-app (visible ya) y, si el usuario lo permite, una de email (la envía el worker)."""
    locale = user.profile.preferred_locale
    title, body = render(kind, locale, data)
    payload = {"title": title, "body": body, "kind": kind, **{k: v for k, v in data.items() if k.endswith("_id")}}
    now = clock.now()
    channels: list[tuple[str, str, datetime | None]] = [("in_app", "SENT", now)]
    if email and user.is_active and not user.anonymized_at and await _email_enabled(session, user.id):
        channels.append(("email", "PENDING", None))
    for channel, status, sent_at in channels:
        stmt = (
            pg_insert(Notification)
            .values(
                id=uuid.uuid4(),
                user_id=user.id,
                type=kind,
                channel=channel,
                status=status,
                payload=payload,
                sent_at=sent_at,
                dedupe_key=dedupe_key,
            )
            .on_conflict_do_nothing(
                index_elements=["user_id", "channel", "dedupe_key"], index_where=Notification.dedupe_key.is_not(None)
            )
        )
        await session.execute(stmt)


async def _email_enabled(session: AsyncSession, user_id: uuid.UUID) -> bool:
    pref = await session.get(NotificationPreference, user_id)
    return pref.email_enabled if pref else True


async def deliver_pending_emails(session: AsyncSession, mailer: Mailer, batch_size: int = 50) -> tuple[int, int]:
    """Envía emails pendientes con reintentos y espera creciente. Un fallo NUNCA afecta a la reserva/pago."""
    now = clock.now()
    rows = (
        (
            await session.execute(
                select(Notification)
                .where(
                    Notification.channel == "email",
                    Notification.status == "PENDING",
                    Notification.attempts < MAX_ATTEMPTS,
                )
                .order_by(Notification.created_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    sent = failed = 0
    for n in rows:
        # backoff exponencial: 1, 2, 4, 8 min tras cada fallo
        if n.attempts and n.updated_at + timedelta(minutes=2 ** (n.attempts - 1)) > now:
            continue
        user = await session.get(User, n.user_id)
        if user is None or not user.is_active:
            n.status, n.last_error = "FAILED", "usuario inactivo"
            continue
        try:
            await mailer.send(Mail(to=user.email, subject=n.payload["title"], body=n.payload["body"]))
            n.status, n.sent_at, n.last_error = "SENT", now, None
            sent += 1
        except Exception as exc:
            n.attempts += 1
            n.last_error = type(exc).__name__  # sin detalles que puedan contener datos personales
            if n.attempts >= MAX_ATTEMPTS:
                n.status = "FAILED"
            failed += 1
            log.warning(
                "email_delivery_failed", event_name="email_failed", notification_id=str(n.id), attempts=n.attempts
            )
    await session.commit()
    return sent, failed


async def list_notifications(
    session: AsyncSession, user_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[Notification], int, int]:
    base = select(Notification).where(Notification.user_id == user_id, Notification.channel == "in_app")
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    unread = (
        await session.execute(select(func.count()).select_from(base.where(Notification.read_at.is_(None)).subquery()))
    ).scalar_one()
    rows = (
        (await session.execute(base.order_by(Notification.created_at.desc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    return list(rows), total, unread


async def mark_read(session: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID) -> None:
    res = await session.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id, Notification.channel == "in_app")
        .values(read_at=clock.now())
    )
    if res.rowcount == 0:  # type: ignore[attr-defined]
        raise NotFoundError("Notificación no encontrada.")
    await session.commit()


async def get_preferences(session: AsyncSession, user_id: uuid.UUID) -> NotificationPreference:
    pref = await session.get(NotificationPreference, user_id)
    if pref is None:
        pref = NotificationPreference(user_id=user_id, email_enabled=True, whatsapp_enabled=False)
        session.add(pref)
        await session.flush()
    return pref


async def update_preferences(
    session: AsyncSession, user_id: uuid.UUID, email_enabled: bool | None, whatsapp_enabled: bool | None
) -> NotificationPreference:
    pref = await get_preferences(session, user_id)
    if email_enabled is not None:
        pref.email_enabled = email_enabled
    if whatsapp_enabled is not None:
        pref.whatsapp_enabled = whatsapp_enabled  # [PENDIENTE P-09] hoy no se envía nada por WhatsApp
    await session.commit()
    await session.refresh(pref)
    return pref
