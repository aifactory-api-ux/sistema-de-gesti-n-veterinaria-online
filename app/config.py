"""Configuración de la aplicación leída del entorno."""

from functools import lru_cache
from secrets import token_urlsafe

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Valores de configuración del proyecto.

    Todos los valores pueden fijarse por variable de entorno o mediante un
    archivo `.env` en la raíz del repositorio. `JWT_SECRET` es la única variable
    sensible: si no se define se genera un secreto aleatorio efímero, apto solo
    para desarrollo local, por lo que en producción es obligatoria.
    """

    DATABASE_URL: str = "postgresql+psycopg://vetclinic:vetclinic@localhost:5432/vetclinic"
    JWT_SECRET: str = Field(default_factory=lambda: token_urlsafe(32))
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    TEST_DATABASE_URL: str = "postgresql+psycopg://vetclinic:vetclinic@localhost:5432/vetclinic_test"
    PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Devuelve la instancia única de configuración de la aplicación."""
    return Settings()


settings = get_settings()
