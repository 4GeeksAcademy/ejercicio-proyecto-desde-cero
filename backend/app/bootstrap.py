"""Arranque de un entorno NUEVO (p. ej. el primer despliegue en Render). Idempotente: se puede ejecutar siempre.

    python -m app.bootstrap

- BOOTSTRAP_OWNER_EMAIL / BOOTSTRAP_OWNER_PASSWORD: crea el primer propietario SOLO si todavía no existe ninguno.
- SEED_DEMO=true: carga los cursos de demostración SOLO si la base de datos no tiene categorías.
"""

import asyncio

import structlog
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import dispose_engine, get_sessionmaker
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.modules.auth.models import Profile, Role, User, UserRole

log = structlog.get_logger()


async def ensure_owner(email: str, password: str) -> bool:
    """Devuelve True si creó el propietario."""
    if len(password) < 10:
        log.error("bootstrap_owner_skipped", reason="la contraseña debe tener al menos 10 caracteres")
        return False
    async with get_sessionmaker()() as s:
        has_owner = (
            await s.execute(
                select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(Role.name == "OWNER").limit(1)
            )
        ).first()
        if has_owner:
            return False
        role = (await s.execute(select(Role).where(Role.name == "OWNER"))).scalar_one()
        user = User(email=email.lower(), password_hash=hash_password(password))
        user.profile = Profile(full_name="Propietario", phone=None, preferred_locale="es")
        user.roles = [role]
        s.add(user)
        await s.commit()
    log.info("bootstrap_owner_created", event_name="bootstrap_owner_created")
    return True


async def run() -> None:
    settings = get_settings()
    if settings.bootstrap_owner_email and settings.bootstrap_owner_password:
        created = await ensure_owner(settings.bootstrap_owner_email, settings.bootstrap_owner_password)
        print("Propietario creado." if created else "Ya existe un propietario: no se hace nada.")
    if settings.seed_demo:
        from app.seed_demo import seed

        await seed()  # ya es idempotente
    await dispose_engine()


if __name__ == "__main__":
    configure_logging()
    asyncio.run(run())
