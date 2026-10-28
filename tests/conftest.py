"""Fixtures y helpers compartidos por la suite de pruebas."""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

# La aplicación lee la configuración al importarse: el entorno de pruebas se fija antes.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "clave-de-pruebas-local-de-la-clinica-veterinaria")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

DEFAULT_PASSWORD = "secreto123"

Base.metadata.create_all(bind=engine)


def _clear_tables() -> None:
    """Vacía las tablas respetando el orden de las claves foráneas."""
    with SessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(delete(table))
        session.commit()


@pytest.fixture(autouse=True)
def reset_database() -> Iterator[None]:
    """Deja las tablas vacías antes y después de cada prueba."""
    _clear_tables()
    yield
    _clear_tables()


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """Cliente HTTP de la aplicación con el ciclo de vida activo."""
    with TestClient(app) as test_client:
        yield test_client


def register_user(
    client: TestClient,
    email: str,
    password: str = DEFAULT_PASSWORD,
    role: str = "client",
) -> dict:
    """Crea una cuenta a través de la API y devuelve su representación."""
    response = client.post(
        "/auth/register", json={"email": email, "password": password, "role": role}
    )
    assert response.status_code == 201, (
        f"No se pudo registrar {email}: {response.status_code} {response.text}"
    )
    return response.json()


def login(
    client: TestClient, email: str, password: str = DEFAULT_PASSWORD
) -> str:
    """Inicia sesión a través de la API y devuelve el token de acceso."""
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, (
        f"No se pudo iniciar sesión como {email}: {response.status_code} {response.text}"
    )
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    """Construye la cabecera Authorization con el token indicado."""
    return {"Authorization": f"Bearer {token}"}
