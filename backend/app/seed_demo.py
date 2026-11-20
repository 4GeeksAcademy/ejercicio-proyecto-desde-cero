"""Datos de demostración (solo desarrollo). Idempotente: si ya hay categorías, no hace nada."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.db import dispose_engine, get_sessionmaker
from app.core.text import slugify
from app.modules.courses.models import Category, CategoryTranslation, Course, CourseTranslation, Venue

CATEGORIES = {
    "ceramica": ("Cerámica", "Ceramics"),
    "fotografia": ("Fotografía", "Photography"),
    "cocina": ("Cocina", "Cooking"),
    "costura": ("Costura", "Sewing"),
    "mecanica": ("Mecánica", "Mechanics"),
    "arte": ("Arte", "Art"),
    "manualidades": ("Manualidades", "Crafts"),
}

# (categoría, es, en, capacidad, precio COP, días hacia adelante, hora inicio, duración h)
COURSES = [
    ("ceramica", "Cerámica para principiantes", "Beginner Ceramics", 5, 180_000, 10, 9, 5),
    (
        "fotografia",
        "Fotografía de retrato con luz natural",
        "Natural Light Portrait Photography",
        8,
        150_000,
        12,
        14,
        4,
    ),
    ("cocina", "Pan de masa madre", "Sourdough Bread", 10, 130_000, 14, 8, 5),
    ("costura", "Tu primera prenda a máquina", "Your First Garment on a Sewing Machine", 6, 160_000, 17, 9, 6),
    ("mecanica", "Mantenimiento básico de tu moto", "Basic Motorcycle Maintenance", 8, 120_000, 19, 8, 4),
    ("arte", "Acuarela para principiantes", "Watercolor for Beginners", 12, 110_000, 21, 15, 3),
    ("manualidades", "Macramé decorativo", "Decorative Macramé", 10, 90_000, 24, 10, 3),
    ("cocina", "Cocina colombiana de autor", "Colombian Fine Cooking", 8, 200_000, 28, 10, 5),
]


async def seed() -> None:
    async with get_sessionmaker()() as s:
        if (await s.execute(select(func.count()).select_from(Category))).scalar_one():
            print("Ya hay datos; no se hace nada.")
        else:
            cats: dict[str, Category] = {}
            for i, (slug, (es, en)) in enumerate(CATEGORIES.items()):
                c = Category(slug=slug, sort_order=i)
                c.translations = [
                    CategoryTranslation(locale="es", name=es, slug=slugify(es)),
                    CategoryTranslation(locale="en", name=en, slug=slugify(en)),
                ]
                cats[slug] = c
            venue = Venue(
                name="Tallerya Sede Chapinero",
                address="Carrera 7 # 56-20, Chapinero",
                city="Bogotá",
                maps_url="https://maps.google.com/?q=Chapinero+Bogota",
            )
            s.add_all([*cats.values(), venue])
            await s.flush()
            base = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
            for cat, es, en, cap, price, days, hour, dur in COURSES:
                start = (base + timedelta(days=days)).replace(hour=hour + 5)  # 09:00 Bogotá = 14:00 UTC
                course = Course(
                    category_id=cats[cat].id,
                    venue_id=venue.id,
                    status="ACTIVE",
                    starts_at=start,
                    ends_at=start + timedelta(hours=dur),
                    capacity=cap,
                    price_minor=price * 100,
                    currency="COP",
                    is_recorded=cat in ("cocina",),
                    recording_status="PLANNED" if cat == "cocina" else "NONE",
                )
                course.translations = [
                    CourseTranslation(
                        locale="es",
                        slug=slugify(es),
                        name=es,
                        short_description=f"Taller presencial de un día: {es.lower()}.",
                        description=f"{es}. Un día completo de práctica guiada en nuestra sede de Chapinero, Bogotá.",
                        materials="Todos los materiales incluidos.",
                        requirements="No se requiere experiencia previa.",
                    ),
                    CourseTranslation(
                        locale="en",
                        slug=slugify(en),
                        name=en,
                        short_description=f"One-day in-person workshop: {en.lower()}.",
                        description=f"{en}. A full day of guided hands-on practice at our Chapinero venue in Bogotá.",
                        materials="All materials included.",
                        requirements="No previous experience required.",
                    ),
                ]
                s.add(course)
            await s.commit()
            print(f"Sembradas {len(CATEGORIES)} categorías y {len(COURSES)} cursos.")
    await dispose_engine()
