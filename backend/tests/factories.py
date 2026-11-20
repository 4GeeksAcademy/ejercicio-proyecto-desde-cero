"""Helpers para crear datos de prueba."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Profile, Role, User
from app.modules.courses.models import Category, CategoryTranslation, Course, CourseTranslation, Venue


async def make_user(s: AsyncSession, email: str | None = None, role: str | None = None) -> User:
    u = User(email=email or f"u{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
    u.profile = Profile(full_name="Test User", preferred_locale="es")
    if role:
        u.roles = [(await s.execute(select(Role).where(Role.name == role))).scalar_one()]
    s.add(u)
    await s.flush()
    return u


async def make_course(
    s: AsyncSession,
    capacity: int = 5,
    hours_ahead: float = 72,
    status: str = "ACTIVE",
    price_minor: int = 100_000,
    slug: str | None = None,
) -> Course:
    slug = slug or f"curso-{uuid.uuid4().hex[:8]}"
    cat = Category(slug=f"cat-{uuid.uuid4().hex[:6]}")
    cat.translations = [CategoryTranslation(locale="es", name="Cerámica", slug=f"c-{uuid.uuid4().hex[:6]}")]
    venue = Venue(name="Sede Chapinero", address="Cra 7 # 45-10")
    s.add_all([cat, venue])
    await s.flush()
    start = datetime.now(UTC) + timedelta(hours=hours_ahead)
    c = Course(
        category_id=cat.id,
        venue_id=venue.id,
        status=status,
        starts_at=start,
        ends_at=start + timedelta(hours=4),
        capacity=capacity,
        price_minor=price_minor,
    )
    c.translations = [
        CourseTranslation(
            locale="es",
            slug=slug,
            name="Cerámica para principiantes",
            short_description="Aprende lo básico",
            description="Descripción completa",
        )
    ]
    s.add(c)
    await s.flush()
    return c
