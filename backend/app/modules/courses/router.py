import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.courses import service
from app.modules.courses.schemas import Availability, CategoryOut, CourseDetail, CoursePage

router = APIRouter(tags=["catalog"])
Locale = Literal["es", "en"]


@router.get("/categories", response_model=list[CategoryOut], summary="Categorías activas")
async def categories(locale: Locale = "es", session: AsyncSession = Depends(get_session)) -> list[CategoryOut]:
    return await service.list_categories(session, locale)


@router.get("/courses", response_model=CoursePage, summary="Buscar y filtrar cursos (solo activos y futuros)")
async def courses(
    locale: Locale = "es",
    q: str | None = Query(None, max_length=100, description="Texto en nombre o descripción corta"),
    category: str | None = Query(None, max_length=120, description="Slug de la categoría en el idioma pedido"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    min_price: int | None = Query(None, ge=0),
    max_price: int | None = Query(None, ge=0),
    language: Locale | None = None,
    available_only: bool = False,
    sort: Literal["date", "price_asc", "price_desc", "newest"] = "date",
    limit: int = Query(12, ge=1, le=50),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> CoursePage:
    items, total = await service.search_courses(
        session,
        locale=locale,
        q=q,
        category=category,
        date_from=date_from,
        date_to=date_to,
        min_price=min_price,
        max_price=max_price,
        language=language,
        available_only=available_only,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return CoursePage(items=items, total=total, limit=limit, offset=offset)


@router.get("/courses/{slug}", response_model=CourseDetail, summary="Detalle de un curso por slug e idioma")
async def course_detail(slug: str, locale: Locale = "es", session: AsyncSession = Depends(get_session)) -> CourseDetail:
    return await service.get_course_by_slug(session, slug, locale)


@router.get("/courses/{course_id}/availability", response_model=Availability, summary="Plazas disponibles")
async def availability(course_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Availability:
    return await service.get_availability(session, course_id)
