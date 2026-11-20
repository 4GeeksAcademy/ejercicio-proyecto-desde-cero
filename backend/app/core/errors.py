"""Sistema de errores.

Distinguimos errores de negocio (esperados, el usuario puede corregirlos) de
errores inesperados (bugs). Al usuario: mensaje comprensible + `code` estable.
Al sistema: log con detalle técnico. Nunca stack traces al usuario.
"""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger()


class AppError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"
    message = "Ha ocurrido un error inesperado."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: Any = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Recurso no encontrado."


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    message = "La operación entra en conflicto con el estado actual."


class BusinessRuleError(AppError):
    status_code = 422
    code = "BUSINESS_RULE_VIOLATION"
    message = "La operación incumple una regla de negocio."


class AuthenticationError(AppError):
    status_code = 401
    code = "NOT_AUTHENTICATED"
    message = "Debes iniciar sesión."


class PermissionDeniedError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    message = "No tienes permiso para esta acción."


class ExternalServiceError(AppError):
    status_code = 502
    code = "EXTERNAL_SERVICE_ERROR"
    message = "Un servicio externo no está disponible."


def _body(code: str, message: str, request: Request, details: Any = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": getattr(request.state, "request_id", None),
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        log.warning("app_error", code=exc.code, status=exc.status_code, error_message=exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(exc.code, exc.message, request, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # No devolvemos el valor enviado (`input`) para no reflejar datos sensibles.
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_body("VALIDATION_ERROR", "Los datos enviados no son válidos.", request, details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 401: "NOT_AUTHENTICATED"}.get(
            exc.status_code, "HTTP_ERROR"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(code, str(exc.detail), request),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error")
        return JSONResponse(
            status_code=500,
            content=_body("INTERNAL_ERROR", "Ha ocurrido un error inesperado.", request),
        )
