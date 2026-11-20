"""Health checks: /health = viva; /ready = lista para recibir tráfico."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.db import check_database

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness: el proceso responde")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness: dependencias disponibles")
async def ready() -> JSONResponse:
    db_ok = await check_database()
    body = {"status": "ready" if db_ok else "not_ready", "checks": {"database": "ok" if db_ok else "fail"}}
    return JSONResponse(status_code=200 if db_ok else 503, content=body)
