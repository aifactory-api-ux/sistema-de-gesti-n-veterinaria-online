"""Configuración de la aplicación leída desde el entorno."""

from functools import lru_cache

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de entorno que la aplicación necesita para arrancar."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    jwt_secret: str
    access_token_expire_minutes: int = 60


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración validada, cacheada durante todo el proceso."""
    try:
        return Settings()
    except ValidationError as error:
        missing = sorted({str(item["loc"][0]).upper() for item in error.errors()})
        raise RuntimeError(
            "Faltan variables de entorno obligatorias: " + ", ".join(missing)
        ) from error
