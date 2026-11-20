"""Tests de integración contra PostgreSQL REAL (no SQLite: necesitamos locks y constraints reales).

Requiere el servicio `db` de docker compose levantado (docker compose up -d db).
"""

import os

os.environ["APP_ENV"] = "testing"
os.environ["POSTGRES_DB"] = "tallerya_test"
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ["BOOKING_RATE_LIMIT_PER_MINUTE"] = "10000"

import psycopg  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import dispose_engine, get_sessionmaker  # noqa: E402

DATA_TABLES = (
    "audit_logs, domain_events, notifications, notification_preferences, commissions, payment_events, "
    "payments, idempotency_keys, booking_status_history, bookings, course_translations, courses, "
    "category_translations, categories, venues, instructors, user_consents, password_reset_tokens, "
    "refresh_tokens, user_roles, profiles, users"
)


def _admin_dsn() -> str:
    s = get_settings()
    return f"host={s.postgres_host} port={s.postgres_port} user={s.postgres_user} password={s.postgres_password} dbname=postgres"


@pytest.fixture(scope="session", autouse=True)
def _database():
    """Crea la BD de test desde cero y aplica TODAS las migraciones (así también las probamos)."""
    try:
        with psycopg.connect(_admin_dsn(), autocommit=True) as conn:
            conn.execute("DROP DATABASE IF EXISTS tallerya_test WITH (FORCE)")
            conn.execute("CREATE DATABASE tallerya_test")
    except psycopg.OperationalError as exc:  # pragma: no cover
        pytest.exit(f"PostgreSQL no disponible: ejecuta 'docker compose up -d db'. ({exc})", returncode=2)
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
async def _clean_tables():
    yield
    async with get_sessionmaker()() as s:
        await s.execute(text(f"TRUNCATE {DATA_TABLES} CASCADE"))
        await s.commit()


@pytest.fixture
async def session():
    async with get_sessionmaker()() as s:
        yield s


@pytest.fixture(scope="session", autouse=True)
async def _dispose_at_end():
    yield
    await dispose_engine()
