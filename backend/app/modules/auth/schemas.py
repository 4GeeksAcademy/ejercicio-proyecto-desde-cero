import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

E164 = re.compile(r"^\+[1-9]\d{7,14}$")
Locale = Literal["es", "en"]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(description="Formato internacional E.164, p. ej. +573001234567")
    preferred_locale: Locale = "es"
    accept_terms: bool = Field(description="Obligatorio: términos y política de privacidad")
    marketing_consent: bool = Field(default=False, description="OPCIONAL. Nunca preseleccionado.")

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        v = re.sub(r"[ \-()]", "", v)
        if not E164.match(v):
            raise ValueError("Teléfono inválido: usa formato internacional, p. ej. +573001234567")
        return v

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre no puede estar vacío")
        return v

    @field_validator("accept_terms")
    @classmethod
    def _terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Debes aceptar los términos y la política de privacidad")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=10, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    full_name: str
    phone: str | None
    preferred_locale: Locale
    roles: list[str]
    permissions: list[str]
    marketing_consent: bool = False
