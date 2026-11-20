"""Lógica de autenticación. Los routers solo traducen HTTP <-> estas funciones."""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, AuthenticationError, ConflictError
from app.core.mail import Mail, Mailer
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    hash_password,
    hash_token,
    needs_rehash,
    new_opaque_token,
    verify_password,
)
from app.modules.audit import service as audit
from app.modules.auth.models import (
    PasswordResetToken,
    Profile,
    RefreshToken,
    Role,
    User,
    UserConsent,
)
from app.modules.auth.schemas import RegisterRequest

log = structlog.get_logger()

TERMS_VERSION = "2026-01"  # versión vigente de los textos legales [PENDIENTE P-14]
MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15
RESET_TOKEN_MINUTES = 60


class EmailTakenError(ConflictError):
    code = "EMAIL_TAKEN"
    message = "Ya existe una cuenta con ese correo."


class AccountLockedError(AppError):
    status_code = 423
    code = "ACCOUNT_LOCKED"
    message = "Cuenta bloqueada temporalmente por demasiados intentos. Inténtalo más tarde."


def _invalid_credentials() -> AuthenticationError:
    # Mismo mensaje exista o no el correo: no revelamos qué cuentas existen.
    return AuthenticationError("Correo o contraseña incorrectos.", code="INVALID_CREDENTIALS")


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return (await session.execute(select(User).where(func.lower(User.email) == email.lower()))).scalar_one_or_none()


async def register(session: AsyncSession, data: RegisterRequest) -> User:
    role = (await session.execute(select(Role).where(Role.name == "CLIENT"))).scalar_one()
    user = User(email=data.email.lower(), password_hash=hash_password(data.password))
    user.profile = Profile(full_name=data.full_name, phone=data.phone, preferred_locale=data.preferred_locale)
    user.roles = [role]
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise EmailTakenError() from exc
    # Consentimientos obligatorios (siempre) y marketing (solo si se marcó explícitamente).
    consents = [
        UserConsent(user_id=user.id, consent_type="terms", document_version=TERMS_VERSION, granted=True),
        UserConsent(user_id=user.id, consent_type="privacy", document_version=TERMS_VERSION, granted=True),
    ]
    if data.marketing_consent:
        consents.append(
            UserConsent(user_id=user.id, consent_type="marketing", document_version=TERMS_VERSION, granted=True)
        )
    session.add_all(consents)
    await session.commit()
    log.info("user_registered", event_name="user_registered", user_id=str(user.id))
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(session, email)
    now = datetime.now(UTC)
    if user is None or not user.is_active or user.anonymized_at:
        verify_password(password, DUMMY_HASH)  # iguala el tiempo de respuesta
        raise _invalid_credentials()
    if user.locked_until and user.locked_until > now:
        raise AccountLockedError()
    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            user.failed_login_count = 0
            log.warning("account_locked", event_name="account_locked", user_id=str(user.id))
        await session.commit()
        raise _invalid_credentials()
    user.failed_login_count = 0
    user.locked_until = None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    await session.commit()
    return user


async def issue_session(session: AsyncSession, user: User, family_id: uuid.UUID | None = None) -> tuple[str, str]:
    """Crea access (JWT) + refresh (opaco, guardado hasheado). Devuelve ambos en claro SOLO para las cookies."""
    s = get_settings()
    raw = new_opaque_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or uuid.uuid4(),
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(days=s.refresh_token_days),
        )
    )
    await session.commit()
    return create_access_token(user.id), raw


async def rotate_refresh(session: AsyncSession, raw_token: str) -> tuple[User, str, str]:
    """Cada refresh se usa UNA vez. Si alguien reutiliza uno ya usado => robo probable: se revoca toda la familia."""
    now = datetime.now(UTC)
    rt = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)).with_for_update()
        )
    ).scalar_one_or_none()
    if rt is None:
        raise AuthenticationError("Sesión no válida.", code="INVALID_SESSION")
    if rt.revoked_at is not None:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == rt.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await session.commit()
        log.warning("refresh_token_reuse_detected", event_name="refresh_reuse", user_id=str(rt.user_id))
        raise AuthenticationError("Sesión no válida.", code="INVALID_SESSION")
    if rt.expires_at <= now:
        raise AuthenticationError("La sesión ha caducado.", code="SESSION_EXPIRED")
    user = await session.get(User, rt.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Sesión no válida.", code="INVALID_SESSION")
    rt.revoked_at = now
    access, new_raw = await issue_session(session, user, family_id=rt.family_id)
    return user, access, new_raw


async def logout(session: AsyncSession, raw_token: str | None) -> None:
    if not raw_token:
        return
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw_token), RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()


async def request_password_reset(session: AsyncSession, email: str, mailer: Mailer) -> None:
    """Siempre 'tiene éxito' para quien llama: no revela si el correo existe."""
    user = await get_user_by_email(session, email)
    if user is None or not user.is_active:
        return
    raw = new_opaque_token()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(minutes=RESET_TOKEN_MINUTES),
        )
    )
    await session.commit()
    locale = user.profile.preferred_locale
    link = f"{get_settings().frontend_url}/{locale}/reset-password?token={raw}"
    subject, body = (
        ("Restablece tu contraseña de Tallerya", f"Usa este enlace (válido {RESET_TOKEN_MINUTES} min):\n{link}")
        if locale == "es"
        else ("Reset your Tallerya password", f"Use this link (valid {RESET_TOKEN_MINUTES} min):\n{link}")
    )
    try:
        await mailer.send(Mail(to=user.email, subject=subject, body=body))
    except Exception:  # un fallo de email no debe romper ni revelar nada
        log.exception("password_reset_email_failed")


async def reset_password(session: AsyncSession, raw_token: str, new_password: str) -> None:
    now = datetime.now(UTC)
    prt = (
        await session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw_token)).with_for_update()
        )
    ).scalar_one_or_none()
    if prt is None or prt.used_at is not None or prt.expires_at <= now:
        raise AuthenticationError("El enlace no es válido o ha caducado.", code="INVALID_RESET_TOKEN")
    user = await session.get(User, prt.user_id)
    if user is None:
        raise AuthenticationError("El enlace no es válido o ha caducado.", code="INVALID_RESET_TOKEN")
    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    prt.used_at = now
    await session.execute(  # cerrar todas las sesiones abiertas
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await audit.record(
        session, actor_id=user.id, action="auth.password_reset", resource_type="user", resource_id=user.id
    )
    await session.commit()
