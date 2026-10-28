"""Fixtures compartidas de la suite de pruebas.

La suite se ejecuta contra un PostgreSQL real, tal y como exige el diseño del
proyecto. La base aislada `vetclinic_test` se crea en el servidor indicado por
`TEST_DATABASE_URL` y, entre pruebas, se vacían sus tablas y se reinician las
secuencias de identificadores.

Si el servidor configurado no está disponible, se levanta un PostgreSQL
embebido para que la suite siga siendo ejecutable en entornos sin servidor de
base de datos. En ese caso hay que instalar el paquete `pgserver`.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app import database as app_database
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import User

logger = logging.getLogger(__name__)

NOMBRE_BASE_PRUEBAS = "vetclinic_test"
EMAIL_CLIENTE = "ana@example.com"
EMAIL_VETERINARIO = "dra.luz@example.com"
CONTRASENA_PRUEBAS = "secreto123"
TIMEOUT_CONEXION_SEGUNDOS = 5

hashador = PasswordHash.recommended()


def _url_con_base(url: str, nombre_base: str) -> str:
    """Devuelve la URL apuntando a otra base del mismo servidor."""
    return make_url(url).set(database=nombre_base).render_as_string(hide_password=False)


def _candidatos_de_url() -> Iterator[str]:
    """URLs candidatas para la base de pruebas, en orden de preferencia."""
    yield os.environ.get("TEST_DATABASE_URL") or settings.TEST_DATABASE_URL
    url_aplicacion = os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    yield _url_con_base(url_aplicacion, NOMBRE_BASE_PRUEBAS)


def _base_accesible(url: str) -> bool:
    """Indica si la base de la URL admite conexiones."""
    motor = create_engine(url, connect_args={"connect_timeout": TIMEOUT_CONEXION_SEGUNDOS})
    try:
        with motor.connect() as conexion:
            conexion.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
    finally:
        motor.dispose()


def _crear_base_si_falta(url: str) -> bool:
    """Crea la base de la URL en su servidor si todavía no existe."""
    nombre_base = make_url(url).database or NOMBRE_BASE_PRUEBAS
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", nombre_base):
        logger.warning("Nombre de base de pruebas no válido: %s", nombre_base)
        return False

    motor = create_engine(
        _url_con_base(url, "postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": TIMEOUT_CONEXION_SEGUNDOS},
    )
    try:
        with motor.connect() as conexion:
            existe = conexion.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :nombre"),
                {"nombre": nombre_base},
            ).scalar()
            if not existe:
                conexion.execute(text(f'CREATE DATABASE "{nombre_base}"'))
                logger.info("Base de pruebas creada: %s", nombre_base)
    except SQLAlchemyError as error:
        logger.warning("No se pudo preparar la base de pruebas %s: %s", nombre_base, error)
        return False
    finally:
        motor.dispose()

    return _base_accesible(url)


def _arrancar_postgres_embebido() -> tuple[Any, str]:
    """Levanta un PostgreSQL embebido y devuelve el servidor y la URL de la base."""
    try:
        import pgserver
    except ImportError as error:
        raise RuntimeError(
            "No hay un PostgreSQL disponible: define TEST_DATABASE_URL con las "
            "credenciales de un servidor accesible o instala el paquete `pgserver`."
        ) from error

    directorio = Path(tempfile.mkdtemp(prefix="vetclinic-pg-"))
    servidor = pgserver.get_server(directorio, cleanup_mode="stop")
    url = f"postgresql+psycopg://postgres@/{NOMBRE_BASE_PRUEBAS}?host={directorio}"
    return servidor, url


def emitir_token(usuario: User) -> str:
    """Emite un JWT con los mismos claims que usa la API: `sub`, `role`, `exp` e `iat`."""
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario.id),
        "role": usuario.role,
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _crear_usuario(sesion_local: sessionmaker[Session], email: str, rol: str) -> User:
    """Inserta un usuario en la base de pruebas y lo devuelve desconectado."""
    usuario = User(
        email=email,
        password_hash=hashador.hash(CONTRASENA_PRUEBAS),
        role=rol,
    )
    with sesion_local() as sesion:
        sesion.add(usuario)
        sesion.commit()
        sesion.refresh(usuario)
        sesion.expunge(usuario)
    return usuario


@pytest.fixture(scope="session")
def _entorno_de_pruebas() -> Iterator[dict[str, Any]]:
    """Deja disponible una base PostgreSQL aislada para toda la suite."""
    url: str | None = None
    for candidato in _candidatos_de_url():
        if _crear_base_si_falta(candidato):
            url = candidato
            break

    servidor = None
    if url is None:
        logger.warning(
            "No se alcanzó el PostgreSQL configurado; se levanta uno embebido para las pruebas."
        )
        servidor, url = _arrancar_postgres_embebido()
        if not _crear_base_si_falta(url):
            raise RuntimeError(f"No se pudo preparar la base de pruebas {url}")

    motor = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(bind=motor)

    with pytest.MonkeyPatch.context() as parche:
        # El arranque de la aplicación crea el esquema sobre la base de pruebas.
        parche.setattr(app_database, "engine", motor)
        yield {"url": url, "motor": motor, "servidor": servidor}

    motor.dispose()
    if servidor is not None:
        servidor.cleanup()


@pytest.fixture(scope="session")
def motor_de_pruebas(_entorno_de_pruebas: dict[str, Any]) -> Engine:
    """Motor SQLAlchemy ligado a la base de pruebas."""
    return _entorno_de_pruebas["motor"]


@pytest.fixture(scope="session")
def sesion_local(_entorno_de_pruebas: dict[str, Any]) -> sessionmaker[Session]:
    """Factoría de sesiones ligadas a la base de pruebas."""
    return sessionmaker(
        bind=_entorno_de_pruebas["motor"],
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


@pytest.fixture
def _base_limpia(motor_de_pruebas: Engine) -> Iterator[None]:
    """Vacía las tablas y reinicia las secuencias antes de cada prueba."""
    with motor_de_pruebas.begin() as conexion:
        conexion.execute(
            text("TRUNCATE TABLE appointments, pets, users RESTART IDENTITY CASCADE")
        )
    yield


@pytest.fixture
def _dependencias_de_base_de_datos(
    sesion_local: sessionmaker[Session], _base_limpia: None
) -> Iterator[None]:
    """Hace que la aplicación use la base de pruebas en lugar de la configurada."""

    def _obtener_sesion() -> Iterator[Session]:
        sesion = sesion_local()
        try:
            yield sesion
        finally:
            sesion.close()

    app.dependency_overrides[get_db] = _obtener_sesion
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(_dependencias_de_base_de_datos: None) -> Iterator[TestClient]:
    """Cliente HTTP que ejercita la aplicación completa, incluido su arranque."""
    with TestClient(app) as cliente:
        yield cliente


@pytest.fixture
def client_user(
    sesion_local: sessionmaker[Session], _base_limpia: None
) -> User:
    """Usuario con rol `client` registrado en la base de pruebas."""
    return _crear_usuario(sesion_local, EMAIL_CLIENTE, "client")


@pytest.fixture
def vet_user(sesion_local: sessionmaker[Session], _base_limpia: None) -> User:
    """Usuario con rol `vet` registrado en la base de pruebas."""
    return _crear_usuario(sesion_local, EMAIL_VETERINARIO, "vet")


@pytest.fixture
def auth_headers(client_user: User) -> dict[str, str]:
    """Cabecera `Authorization: Bearer` con un token válido de cliente."""
    return {"Authorization": f"Bearer {emitir_token(client_user)}"}
