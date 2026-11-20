import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.modules.audit import service as audit
from app.modules.auth.dependencies import Principal
from app.modules.auth.models import RefreshToken, User, UserConsent
from app.modules.auth.schemas import UserOut
from app.modules.auth.service import TERMS_VERSION
from app.modules.bookings.models import SEAT_HOLDING_STATUSES, Booking
from app.modules.courses.models import Course


async def marketing_consent_granted(session: AsyncSession, user_id: uuid.UUID) -> bool:
    latest = (
        await session.execute(
            select(UserConsent.granted)
            .where(UserConsent.user_id == user_id, UserConsent.consent_type == "marketing")
            .order_by(UserConsent.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return bool(latest)


async def to_user_out(session: AsyncSession, principal: Principal) -> UserOut:
    u = principal.user
    return UserOut(
        id=u.id,
        email=u.email,
        full_name=u.profile.full_name,
        phone=u.profile.phone,
        preferred_locale=u.profile.preferred_locale,
        roles=sorted(principal.roles),
        permissions=sorted(principal.permissions),
        marketing_consent=await marketing_consent_granted(session, u.id),
    )


async def update_profile(session: AsyncSession, user: User, changes: dict[str, str]) -> None:
    for field, value in changes.items():
        setattr(user.profile, field, value)
    await session.commit()


async def set_marketing_consent(session: AsyncSession, user: User, granted: bool, source: str = "web") -> None:
    """Cada cambio queda registrado (otorgar/revocar), con versión del texto y fecha."""
    session.add(
        UserConsent(
            user_id=user.id, consent_type="marketing", document_version=TERMS_VERSION, granted=granted, source=source
        )
    )
    await session.commit()


async def anonymize_account(session: AsyncSession, user: User) -> None:
    """Derecho de supresión: se anonimiza (los datos contables de reservas/pagos se conservan sin identificar).

    No se permite con reservas vivas de cursos futuros. Plazos/obligaciones legales: [PENDIENTE P-14].
    """
    now = datetime.now(UTC)
    active = (
        await session.execute(
            select(Booking.id)
            .join(Course, Course.id == Booking.course_id)
            .where(
                Booking.user_id == user.id,
                Booking.status.in_([s.value for s in SEAT_HOLDING_STATUSES]),
                Course.ends_at > now,
            )
            .limit(1)
        )
    ).first()
    if active:
        raise ConflictError(
            "Tienes reservas activas. Cancélalas o espera a que finalicen para eliminar tu cuenta.",
            code="ACTIVE_BOOKINGS_EXIST",
        )
    user.email = f"deleted-{user.id}@anonymized.invalid"
    user.is_active = False
    user.anonymized_at = now
    user.password_hash = "!"  # noqa: S105 (marcador: no es un hash válido, nadie podrá iniciar sesión)
    user.profile.full_name = "Usuario eliminado"
    user.profile.phone = None
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await audit.record(session, actor_id=user.id, action="user.anonymized", resource_type="user", resource_id=user.id)
    await session.commit()
