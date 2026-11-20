from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AuthenticationError
from app.core.mail import Mailer, get_mailer
from app.core.rate_limit import rate_limit
from app.core.security import new_opaque_token
from app.modules.auth import service
from app.modules.auth.dependencies import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE, principal_for
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserOut,
)
from app.modules.users.service import to_user_out

router = APIRouter(prefix="/auth", tags=["auth"])

_login_limit = rate_limit("login", limit=10, window_seconds=60)
_register_limit = rate_limit("register", limit=5, window_seconds=60)
_forgot_limit = rate_limit("forgot", limit=5, window_seconds=60)

REFRESH_PATH = "/api/v1/auth"


def _cookie(response: Response, name: str, value: str, max_age: int, httponly: bool, path: str) -> None:
    response.set_cookie(
        name, value, max_age=max_age, httponly=httponly, path=path, secure=get_settings().cookie_secure, samesite="lax"
    )


def _set_cookies(response: Response, access: str, refresh: str) -> None:
    s = get_settings()
    _cookie(response, ACCESS_COOKIE, access, s.access_token_minutes * 60, True, "/")
    _cookie(response, REFRESH_COOKIE, refresh, s.refresh_token_days * 86400, True, REFRESH_PATH)
    # Cookie CSRF legible por JS (no httpOnly) para reenviarla en la cabecera X-CSRF-Token.
    _cookie(response, CSRF_COOKIE, new_opaque_token(), s.refresh_token_days * 86400, False, "/")


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)


async def _session_response(
    session: AsyncSession, user: User, response: Response, access: str, refresh: str
) -> UserOut:
    _set_cookies(response, access, refresh)
    return await to_user_out(session, principal_for(user))


@router.post("/register", status_code=201, response_model=UserOut, dependencies=[Depends(_register_limit)])
async def register(body: RegisterRequest, response: Response, session: AsyncSession = Depends(get_session)) -> UserOut:
    user = await service.register(session, body)
    access, refresh = await service.issue_session(session, user)
    return await _session_response(session, user, response, access, refresh)


@router.post("/login", response_model=UserOut, dependencies=[Depends(_login_limit)])
async def login(body: LoginRequest, response: Response, session: AsyncSession = Depends(get_session)) -> UserOut:
    user = await service.authenticate(session, body.email, body.password)
    access, refresh = await service.issue_session(session, user)
    return await _session_response(session, user, response, access, refresh)


@router.post("/refresh", response_model=UserOut, summary="Renueva la sesión (rota el refresh token)")
async def refresh(request: Request, response: Response, session: AsyncSession = Depends(get_session)) -> UserOut:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise AuthenticationError()
    user, access, new_refresh = await service.rotate_refresh(session, raw)
    return await _session_response(session, user, response, access, new_refresh)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, session: AsyncSession = Depends(get_session)) -> Response:
    await service.logout(session, request.cookies.get(REFRESH_COOKIE))
    _clear_cookies(response)
    response.status_code = 204
    return response


@router.post("/forgot-password", status_code=202, dependencies=[Depends(_forgot_limit)])
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_session),
    mailer: Mailer = Depends(get_mailer),
) -> dict[str, str]:
    await service.request_password_reset(session, body.email, mailer)
    return {"message": "Si el correo existe, recibirás instrucciones para restablecer tu contraseña."}


@router.post("/reset-password", status_code=204, dependencies=[Depends(_forgot_limit)])
async def reset_password(body: ResetPasswordRequest, session: AsyncSession = Depends(get_session)) -> Response:
    await service.reset_password(session, body.token, body.new_password)
    return Response(status_code=204)
