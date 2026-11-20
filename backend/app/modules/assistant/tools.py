"""Herramientas de SOLO LECTURA para un futuro asistente de IA (Hito 15).

Principios (ver docs/adr/0007-asistente-ia.md):
  1. El asistente solo ve información REAL: cada herramienta llama a los mismos servicios que el catálogo web.
  2. Devuelve IDs y datos mínimos; la interfaz pinta precio/fecha/cupos desde la BD, nunca desde texto generado.
  3. NO existen herramientas de reservar ni pagar: eso sigue pasando por la API normal con autenticación,
     reglas de negocio y confirmación del usuario. Una IA no puede saltarse las reglas.
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, BusinessRuleError
from app.modules.courses import service as courses

Locale = Literal["es", "en"]


class SearchCoursesArgs(BaseModel):
    query: str | None = Field(default=None, max_length=100, description="Texto libre: tema, técnica, palabra clave")
    category: str | None = Field(default=None, max_length=120, description="Slug de categoría (ver list_categories)")
    date_from: datetime | None = None
    date_to: datetime | None = None
    max_price_cop: int | None = Field(default=None, ge=0, description="Precio máximo en pesos colombianos")
    available_only: bool = True
    locale: Locale = "es"
    limit: int = Field(default=5, ge=1, le=10)


class GetCourseDetailsArgs(BaseModel):
    slug: str = Field(max_length=160)
    locale: Locale = "es"


class BusinessInfoArgs(BaseModel):
    locale: Locale = "es"


def public_course_url(locale: str, slug: str) -> str:
    """URL pública del curso. Debe coincidir con las rutas del frontend (frontend/i18n/routing.ts)."""
    base = get_settings().frontend_url.rstrip("/")
    return f"{base}/es/cursos/{slug}" if locale == "es" else f"{base}/en/courses/{slug}"


def business_info(locale: str) -> dict[str, Any]:
    base = get_settings().frontend_url.rstrip("/")
    es = locale == "es"
    return {
        "name": "Tallerya",
        "website": f"{base}/{locale}",
        "catalog_url": f"{base}/es/cursos" if es else f"{base}/en/courses",
        "faq_url": f"{base}/es/preguntas-frecuentes" if es else f"{base}/en/faq",
        "contact_url": f"{base}/es/contacto" if es else f"{base}/en/contact",
        "city": "Bogotá",
        "country": "Colombia",
        "timezone": "America/Bogota",
        "description": (
            "Academia de talleres presenciales de un día: cerámica, fotografía, cocina, costura, mecánica, arte y manualidades."
            if es
            else "Academy of one-day in-person workshops: ceramics, photography, cooking, sewing, mechanics, art and crafts."
        ),
        "languages": ["es", "en"],
        "booking_rules": (
            "Una reserva por persona; no se reserva con menos de 24 h de antelación; 24 h para pagar; se cancela si faltan más de 24 h. "
            "Reservar y pagar se hace en el sitio web con una cuenta."
            if es
            else "One booking per person; no bookings within 24 h of the start; 24 h to pay; cancellable if more than 24 h remain. "
            "Booking and payment are done on the website with an account."
        ),
    }


class CheckAvailabilityArgs(BaseModel):
    course_id: uuid.UUID


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "search_courses",
        "description": "Busca talleres reales de Tallerya (activos y futuros). Devuelve como mucho 10. No inventes cursos: usa solo lo devuelto.",
        "input_schema": SearchCoursesArgs.model_json_schema(),
    },
    {
        "name": "get_course_details",
        "description": "Detalle de un curso por su slug (descripción, materiales, requisitos, lugar).",
        "input_schema": GetCourseDetailsArgs.model_json_schema(),
    },
    {
        "name": "get_business_info",
        "description": "Datos de Tallerya (nombre, ciudad, URL del sitio, catálogo, contacto y reglas de reserva). Úsala para dar la URL del negocio.",
        "input_schema": BusinessInfoArgs.model_json_schema(),
    },
    {
        "name": "check_availability",
        "description": "Plazas disponibles AHORA de un curso y si todavía se puede reservar.",
        "input_schema": CheckAvailabilityArgs.model_json_schema(),
    },
]
READ_ONLY_TOOLS = {t["name"] for t in TOOL_DEFINITIONS}


async def execute_tool(session: AsyncSession, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta una herramienta. Los errores se devuelven como dato (el modelo puede explicarlos), nunca como excepción."""
    if name not in READ_ONLY_TOOLS:
        return {"error": "unknown_tool", "message": f"Herramienta no disponible: {name}"}
    try:
        if name == "search_courses":
            a = SearchCoursesArgs.model_validate(arguments)
            items, total = await courses.search_courses(
                session,
                locale=a.locale,
                q=a.query,
                category=a.category,
                date_from=a.date_from,
                date_to=a.date_to,
                min_price=None,
                max_price=a.max_price_cop * 100 if a.max_price_cop is not None else None,
                language=None,
                available_only=a.available_only,
                sort="date",
                limit=a.limit,
                offset=0,
            )
            return {
                "total_matching": total,
                "courses": [
                    {
                        "id": str(c.id),
                        "slug": c.slug,
                        "name": c.name,
                        "category": c.category.name,
                        "url": public_course_url(a.locale, c.slug),
                        "starts_at": c.starts_at.isoformat(),
                        "price_minor": c.price_minor,
                        "currency": c.currency,
                        "seats_available": c.seats_available,
                    }
                    for c in items
                ],
            }
        if name == "get_course_details":
            a2 = GetCourseDetailsArgs.model_validate(arguments)
            d = await courses.get_course_by_slug(session, a2.slug, a2.locale)
            return {
                "id": str(d.id),
                "slug": d.slug,
                "name": d.name,
                "short_description": d.short_description,
                "url": public_course_url(a2.locale, d.slug),
                "urls_by_locale": {loc: public_course_url(loc, slug) for loc, slug in d.alternates.items()},
                "venue_name": d.venue.name,
                "venue_city": d.venue.city,
                "maps_url": d.venue.maps_url,
                "description": d.description[:1500],
                "materials": d.materials,
                "requirements": d.requirements,
                "starts_at": d.starts_at.isoformat(),
                "ends_at": d.ends_at.isoformat(),
                "venue": d.venue.address,
                "price_minor": d.price_minor,
                "currency": d.currency,
                "seats_available": d.seats_available,
                "booking_open": d.booking_open,
            }
        if name == "get_business_info":
            return business_info(BusinessInfoArgs.model_validate(arguments).locale)
        a3 = CheckAvailabilityArgs.model_validate(arguments)
        av = await courses.get_availability(session, a3.course_id)
        return av.model_dump(mode="json")
    except ValidationError as exc:
        return {"error": "invalid_arguments", "message": "; ".join(e["msg"] for e in exc.errors())[:300]}
    except (AppError, BusinessRuleError) as exc:
        return {"error": exc.code, "message": exc.message}
