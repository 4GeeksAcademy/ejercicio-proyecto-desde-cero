"""Configuración de la aplicación.

QUÉ es: un objeto que lee variables de entorno y las valida al arrancar.
PARA QUÉ: no tener secretos en el código y poder cambiar de entorno
(development/testing/staging/production) sin tocar código.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore", case_sensitive=False)

    app_env: Literal["development", "testing", "staging", "production"] = "development"
    log_level: str = "INFO"
    service_name: str = "tallerya-api"

    postgres_user: str = "tallerya"
    postgres_password: str = "tallerya"
    postgres_db: str = "tallerya"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    cors_allowed_origins: str = "http://localhost:3000"

    # Auth (Hito 3). En producción DEBE venir del entorno.
    jwt_secret: str = Field(default="dev-only-change-me-please-32-bytes-min")
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    cookie_secure: bool = False

    # Reglas de negocio configurables (Hito 5/6)
    booking_payment_window_hours: int = 24
    booking_cutoff_hours: int = 24
    default_commission_bps: int = 2000  # 20 % [CLIENTE], configurable

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
