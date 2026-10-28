"""Pruebas del contrato de configuración que la aplicación lee del entorno."""

import pytest
from sqlalchemy import create_engine

from app.config import get_settings

# URL de ejemplo de PostgreSQL con el esquema que resuelve el driver psycopg 3.
URL_POSTGRES = "postgresql+psycopg://clinic:clinic@db:5432/clinic"


def test_settings_exigen_el_url_de_base_de_datos(monkeypatch, tmp_path):
    """Sin DATABASE_URL la aplicación falla al arrancar con un error claro."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_settings()

    get_settings.cache_clear()


def test_settings_exigen_el_secreto_jwt(monkeypatch, tmp_path):
    """Sin JWT_SECRET la aplicación falla al arrancar con un error claro."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        get_settings()

    get_settings.cache_clear()


def test_settings_leen_las_variables_del_entorno(monkeypatch, tmp_path):
    """Las variables del entorno alimentan la configuración de la aplicación."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", URL_POSTGRES)
    monkeypatch.setenv("JWT_SECRET", "clave-de-prueba-local")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url == URL_POSTGRES
    assert settings.jwt_secret == "clave-de-prueba-local"
    assert settings.access_token_expire_minutes == 15

    get_settings.cache_clear()


def test_el_motor_acepta_el_esquema_de_url_de_postgres():
    """Una URL de PostgreSQL la resuelve SQLAlchemy con el driver psycopg 3."""
    engine = create_engine(URL_POSTGRES)

    assert engine.dialect.driver == "psycopg"
