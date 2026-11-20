from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.dependencies import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE, Principal, get_current_principal
from app.modules.auth.schemas import Locale, UserOut
from app.modules.users import service

router = APIRouter(prefix="/users", tags=["users"])


class ProfileUpdate(BaseModel):
    full_name: Annotated[str | None, Field(min_length=1, max_length=120)] = None
    phone: Annotated[str | None, Field(pattern=r"^\+[1-9]\d{7,14}$")] = None
    preferred_locale: Locale | None = None


class ConsentUpdate(BaseModel):
    marketing: bool


@router.get("/me", response_model=UserOut, summary="Mi perfil")
async def get_me(
    principal: Principal = Depends(get_current_principal), session: AsyncSession = Depends(get_session)
) -> UserOut:
    return await service.to_user_out(session, principal)


@router.patch("/me", response_model=UserOut, summary="Actualizar mi perfil")
async def update_me(
    body: ProfileUpdate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    await service.update_profile(session, principal.user, body.model_dump(exclude_none=True))
    return await service.to_user_out(session, principal)


@router.put("/me/consents", response_model=UserOut, summary="Cambiar consentimiento de marketing (opcional)")
async def set_consents(
    body: ConsentUpdate,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    await service.set_marketing_consent(session, principal.user, body.marketing)
    return await service.to_user_out(session, principal)


@router.delete("/me", status_code=204, summary="Eliminar (anonimizar) mi cuenta")
async def delete_me(
    response: Response,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await service.anonymize_account(session, principal.user)
    for c in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(c, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    response.status_code = 204
    return response
