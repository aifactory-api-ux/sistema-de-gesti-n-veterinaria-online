"""Pruebas del registro, del inicio de sesión y de la protección por token Bearer."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.dependencies import get_current_user, require_client
from app.models import User
from app.security import emitir_token

CONTRASENA = "secreto123"


def _registrar(
    client: TestClient, email: str, rol: str = "client", contrasena: str = CONTRASENA
) -> dict:
    """Registra un usuario mediante la API y devuelve el cuerpo de la respuesta."""
    respuesta = client.post(
        "/auth/register",
        json={"email": email, "password": contrasena, "role": rol},
    )
    assert respuesta.status_code == 201
    return respuesta.json()


def _token_expirado() -> str:
    """Emite un token ya caducado, firmado con el secreto de la aplicación."""
    ahora = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": "1",
            "role": "client",
            "iat": int((ahora - timedelta(hours=2)).timestamp()),
            "exp": int((ahora - timedelta(hours=1)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


# --- Registro ---------------------------------------------------------------


def test_registro_de_un_cliente_responde_201(client: TestClient) -> None:
    respuesta = client.post(
        "/auth/register",
        json={"email": "ana@example.com", "password": CONTRASENA, "role": "client"},
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"id", "email", "role"}
    assert cuerpo["email"] == "ana@example.com"
    assert cuerpo["role"] == "client"
    assert isinstance(cuerpo["id"], int)


def test_registro_de_un_veterinario_responde_201(client: TestClient) -> None:
    respuesta = client.post(
        "/auth/register",
        json={"email": "dra.luz@example.com", "password": CONTRASENA, "role": "vet"},
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"id", "email", "role"}
    assert cuerpo["email"] == "dra.luz@example.com"
    assert cuerpo["role"] == "vet"


def test_registro_normaliza_el_email_a_minusculas(client: TestClient) -> None:
    respuesta = client.post(
        "/auth/register",
        json={"email": "Ana@Example.com", "password": CONTRASENA, "role": "client"},
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["email"] == "ana@example.com"


def test_registro_con_email_duplicado_responde_409(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _registrar(client, "ana@example.com")

    respuesta = client.post(
        "/auth/register",
        json={"email": "ana@example.com", "password": "otraClave9", "role": "vet"},
    )

    assert respuesta.status_code == 409
    assert "id" not in respuesta.json()
    with sesion_local() as sesion:
        total = sesion.scalar(
            select(func.count()).select_from(User).where(User.email == "ana@example.com")
        )
    assert total == 1


def test_registro_con_contrasena_de_seis_caracteres_responde_422(
    client: TestClient,
) -> None:
    respuesta = client.post(
        "/auth/register",
        json={"email": "corto@example.com", "password": "corta7", "role": "client"},
    )

    assert respuesta.status_code == 422


def test_registro_con_contrasena_de_ocho_caracteres_responde_201(
    client: TestClient,
) -> None:
    respuesta = client.post(
        "/auth/register",
        json={"email": "ocho@example.com", "password": "12345678", "role": "client"},
    )

    assert respuesta.status_code == 201


def test_registro_con_rol_invalido_responde_422(client: TestClient) -> None:
    respuesta = client.post(
        "/auth/register",
        json={"email": "admin@example.com", "password": CONTRASENA, "role": "admin"},
    )

    assert respuesta.status_code == 422


def test_registro_sin_rol_responde_422(client: TestClient) -> None:
    respuesta = client.post(
        "/auth/register",
        json={"email": "sinrol@example.com", "password": CONTRASENA},
    )

    assert respuesta.status_code == 422


def test_registro_guarda_el_hash_y_no_la_contrasena(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _registrar(client, "ana@example.com")

    with sesion_local() as sesion:
        usuario = sesion.scalar(select(User).where(User.email == "ana@example.com"))

    assert usuario is not None
    assert usuario.password_hash != CONTRASENA
    assert CONTRASENA not in usuario.password_hash
    assert usuario.password_hash.startswith("$argon2")


# --- Inicio de sesión -------------------------------------------------------


def test_login_valido_responde_200_con_token(client: TestClient) -> None:
    _registrar(client, "ana@example.com")

    respuesta = client.post(
        "/auth/login", json={"email": "ana@example.com", "password": CONTRASENA}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"access_token", "token_type"}
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["access_token"]


def test_login_con_contrasena_incorrecta_responde_401(client: TestClient) -> None:
    _registrar(client, "ana@example.com")

    respuesta = client.post(
        "/auth/login", json={"email": "ana@example.com", "password": "claveMala1"}
    )

    assert respuesta.status_code == 401
    assert "access_token" not in respuesta.json()


def test_login_con_email_inexistente_responde_401(client: TestClient) -> None:
    respuesta = client.post(
        "/auth/login", json={"email": "nadie@example.com", "password": CONTRASENA}
    )

    assert respuesta.status_code == 401
    assert "access_token" not in respuesta.json()


def test_login_no_devuelve_material_de_contrasena(client: TestClient) -> None:
    _registrar(client, "ana@example.com")

    respuesta = client.post(
        "/auth/login", json={"email": "ana@example.com", "password": CONTRASENA}
    )

    assert respuesta.status_code == 200
    assert "password" not in respuesta.text
    assert "password_hash" not in respuesta.text
    assert CONTRASENA not in respuesta.text


def test_el_token_identifica_al_usuario_y_a_su_rol(
    sesion_local: sessionmaker[Session], vet_user: User
) -> None:
    credenciales = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=emitir_token(vet_user.id, vet_user.role)
    )

    with sesion_local() as sesion:
        usuario = get_current_user(credenciales=credenciales, db=sesion)

    assert usuario.id == vet_user.id
    assert usuario.email == vet_user.email
    assert usuario.role == "vet"


# --- Protección por token Bearer --------------------------------------------


def test_peticion_sin_cabecera_authorization_responde_401(client: TestClient) -> None:
    respuesta = client.get("/pets")

    assert respuesta.status_code == 401
    assert "detail" in respuesta.json()


def test_token_con_firma_invalida_responde_401(client: TestClient) -> None:
    respuesta = client.get(
        "/pets", headers={"Authorization": "Bearer token.inventado.aaa"}
    )

    assert respuesta.status_code == 401


def test_token_expirado_responde_401(client: TestClient) -> None:
    respuesta = client.get(
        "/pets", headers={"Authorization": f"Bearer {_token_expirado()}"}
    )

    assert respuesta.status_code == 401


def test_esquema_de_autorizacion_distinto_de_bearer_responde_401(
    client: TestClient,
) -> None:
    respuesta = client.get("/pets", headers={"Authorization": "Basic dXNlcjpwYXNz"})

    assert respuesta.status_code == 401


def test_token_valido_no_responde_401(
    client: TestClient, client_user: User
) -> None:
    respuesta = client.get(
        "/pets", headers={"Authorization": f"Bearer {emitir_token(client_user.id, client_user.role)}"}
    )

    assert respuesta.status_code != 401


def test_get_current_user_responde_401_sin_token(
    sesion_local: sessionmaker[Session],
) -> None:
    with sesion_local() as sesion:
        with pytest.raises(HTTPException) as excepcion:
            get_current_user(credenciales=None, db=sesion)

    assert excepcion.value.status_code == 401


def test_require_client_responde_403_para_un_veterinario(vet_user: User) -> None:
    with pytest.raises(HTTPException) as excepcion:
        require_client(vet_user)

    assert excepcion.value.status_code == 403


def test_require_client_devuelve_el_usuario_para_un_cliente(client_user: User) -> None:
    assert require_client(client_user) is client_user
