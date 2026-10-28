"""Pruebas del registro, el inicio de sesión y la protección con token bearer."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.dependencies import get_current_user, require_client, resolve_current_user
from app.models import User
from app.security import create_access_token
from tests.conftest import DEFAULT_PASSWORD, auth_header, login, register_user

FOREIGN_SECRET = "una-clave-que-no-es-la-del-servidor"


def _futuro() -> str:
    """Devuelve un instante ISO 8601 dentro del horario de atención."""
    inicio = datetime.now(timezone.utc) + timedelta(days=7)
    return inicio.strftime("%Y-%m-%dT%H:%M:%SZ")


ENDPOINTS_PROTEGIDOS = [
    ("GET", "/vets", None),
    (
        "POST",
        "/pets",
        {"name": "Firulais", "species": "dog", "birth_date": "2021-03-15"},
    ),
    ("GET", "/pets", None),
    (
        "POST",
        "/appointments",
        {"pet_id": 1, "vet_id": 1, "start_at": _futuro()},
    ),
    ("GET", "/appointments", None),
    ("POST", "/appointments/1/cancel", None),
]

CABECERAS_MAL_FORMADAS = [
    {"Authorization": "Bearer"},
    {"Authorization": "Token un.token.invalido"},
    {"Authorization": "sin-esquema"},
]


def _request(
    client: TestClient,
    method: str,
    path: str,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
):
    """Ejecuta la petición indicada con cuerpo y cabeceras opcionales."""
    if body is None:
        return client.request(method, path, headers=headers)
    return client.request(method, path, json=body, headers=headers)


def _stored_user(email: str) -> User:
    """Devuelve la cuenta persistida con el correo indicado."""
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == email))
        assert user is not None, f"No se encontró la cuenta {email}"
        return user


def _foreign_token(user_id: int, role: str) -> str:
    """Emite un token estructuralmente válido firmado con otra clave."""
    issued_at = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "role": role,
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=60),
        },
        FOREIGN_SECRET,
        algorithm="HS256",
    )


def test_registro_de_un_cliente_responde_201_con_id_email_y_rol(
    client: TestClient,
) -> None:
    """El registro de un cliente devuelve su identificador, correo y rol."""
    response = client.post(
        "/auth/register",
        json={"email": "ana@example.com", "password": DEFAULT_PASSWORD, "role": "client"},
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "email", "role"}
    assert isinstance(body["id"], int)
    assert body["email"] == "ana@example.com"
    assert body["role"] == "client"


def test_registro_de_un_veterinario_responde_201_con_rol_vet(
    client: TestClient,
) -> None:
    """El registro de un veterinario devuelve el rol `vet`."""
    response = client.post(
        "/auth/register",
        json={
            "email": "dra.solis@example.com",
            "password": DEFAULT_PASSWORD,
            "role": "vet",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "vet"


def test_la_respuesta_de_registro_no_contiene_la_contrasena(client: TestClient) -> None:
    """Ni la contraseña ni su hash aparecen en la respuesta del registro."""
    response = client.post(
        "/auth/register",
        json={"email": "ana@example.com", "password": DEFAULT_PASSWORD, "role": "client"},
    )

    assert response.status_code == 201
    body = response.json()
    assert "password" not in body
    assert "hashed_password" not in body
    assert DEFAULT_PASSWORD not in response.text
    assert _stored_user("ana@example.com").hashed_password not in response.text


def test_registro_con_rol_fuera_de_client_y_vet_responde_422(
    client: TestClient,
) -> None:
    """Un rol desconocido se rechaza y no crea ninguna cuenta."""
    response = client.post(
        "/auth/register",
        json={"email": "admin@example.com", "password": DEFAULT_PASSWORD, "role": "admin"},
    )

    assert response.status_code == 422
    with SessionLocal() as session:
        assert session.scalar(select(User).where(User.email == "admin@example.com")) is None


def test_registro_con_contrasena_de_siete_caracteres_responde_422(
    client: TestClient,
) -> None:
    """Una contraseña de menos de ocho caracteres se rechaza."""
    response = client.post(
        "/auth/register",
        json={"email": "corto@example.com", "password": "1234567", "role": "client"},
    )

    assert response.status_code == 422
    with SessionLocal() as session:
        assert session.scalar(select(User).where(User.email == "corto@example.com")) is None


def test_registro_con_contrasena_de_ocho_caracteres_responde_201(
    client: TestClient,
) -> None:
    """Una contraseña de exactamente ocho caracteres se acepta."""
    response = client.post(
        "/auth/register",
        json={"email": "ocho@example.com", "password": "12345678", "role": "client"},
    )

    assert response.status_code == 201


def test_registro_con_correo_duplicado_responde_409(client: TestClient) -> None:
    """El correo ya registrado se rechaza y la cuenta original no cambia."""
    register_user(client, "ana@example.com", role="client")

    response = client.post(
        "/auth/register",
        json={"email": "ana@example.com", "password": "otraclave", "role": "vet"},
    )

    assert response.status_code == 409
    almacenada = _stored_user("ana@example.com")
    assert almacenada.role == "client"
    assert almacenada.hashed_password != "otraclave"


def test_login_con_credenciales_validas_responde_200_con_token_bearer(
    client: TestClient,
) -> None:
    """El inicio de sesión válido devuelve un token de tipo bearer."""
    register_user(client, "ana@example.com")

    response = client.post(
        "/auth/login", json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["access_token"]


def test_el_token_devuelto_es_un_jwt_con_identidad_rol_y_expiracion(
    client: TestClient,
) -> None:
    """El token emitido tiene tres segmentos y claims de identidad y expiración."""
    cuenta = register_user(client, "ana@example.com")

    token = login(client, "ana@example.com")
    assert token.count(".") == 2

    payload = jwt.decode(
        token, get_settings().jwt_secret, algorithms=["HS256"]
    )
    assert payload["sub"] == str(cuenta["id"])
    assert payload["role"] == "client"
    assert payload["exp"] > payload["iat"]


def test_login_con_contrasena_incorrecta_responde_401(client: TestClient) -> None:
    """Una contraseña que no corresponde a la cuenta se rechaza."""
    register_user(client, "ana@example.com")

    response = client.post(
        "/auth/login", json={"email": "ana@example.com", "password": "incorrecta"}
    )

    assert response.status_code == 401


def test_login_con_correo_desconocido_responde_401(client: TestClient) -> None:
    """Un correo sin cuenta se rechaza."""
    response = client.post(
        "/auth/login", json={"email": "nadie@example.com", "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 401


def test_la_contrasena_almacenada_no_es_el_texto_plano(client: TestClient) -> None:
    """La cuenta guarda un hash con sal, no la contraseña enviada."""
    register_user(client, "ana@example.com", password=DEFAULT_PASSWORD)

    almacenada = _stored_user("ana@example.com")
    assert almacenada.hashed_password != DEFAULT_PASSWORD
    assert almacenada.hashed_password.startswith("$argon2")


def test_un_token_recien_emitido_es_aceptado_por_la_dependencia(
    client: TestClient,
) -> None:
    """La dependencia resuelve la cuenta a partir de un token recién emitido."""
    cuenta = register_user(client, "ana@example.com")
    token = create_access_token(user_id=cuenta["id"], role="client")

    with SessionLocal() as session:
        usuario = resolve_current_user(session, token)
        assert usuario.id == cuenta["id"]
        assert usuario.email == "ana@example.com"
        assert usuario.role == "client"


def test_un_token_firmado_con_otra_clave_es_rechazado(client: TestClient) -> None:
    """Un token firmado con otra clave no resuelve ninguna cuenta."""
    cuenta = register_user(client, "ana@example.com")
    token = _foreign_token(cuenta["id"], "client")

    with SessionLocal() as session, pytest.raises(HTTPException) as error:
        resolve_current_user(session, token)

    assert error.value.status_code == 401


def test_un_token_expirado_es_rechazado(client: TestClient) -> None:
    """Un token cuyo vencimiento ya pasó no resuelve ninguna cuenta."""
    cuenta = register_user(client, "ana@example.com")
    token = create_access_token(user_id=cuenta["id"], role="client", expires_minutes=-1)

    with SessionLocal() as session, pytest.raises(HTTPException) as error:
        resolve_current_user(session, token)

    assert error.value.status_code == 401


def test_un_token_inexistente_es_rechazado(client: TestClient) -> None:
    """Un token cuyo sujeto no corresponde a una cuenta no resuelve nada."""
    token = create_access_token(user_id=9999, role="client")

    with SessionLocal() as session, pytest.raises(HTTPException) as error:
        resolve_current_user(session, token)

    assert error.value.status_code == 401


def test_sin_credenciales_la_dependencia_responde_401() -> None:
    """Una petición sin cabecera Authorization se rechaza con 401."""
    with SessionLocal() as session, pytest.raises(HTTPException) as error:
        get_current_user(None, session)

    assert error.value.status_code == 401


def test_require_client_rechaza_a_un_veterinario(client: TestClient) -> None:
    """Un veterinario no puede usar las operaciones reservadas a clientes."""
    cuenta = register_user(client, "dra.solis@example.com", role="vet")

    with SessionLocal() as session:
        usuario = resolve_current_user(
            session, create_access_token(user_id=cuenta["id"], role="vet")
        )
        with pytest.raises(HTTPException) as error:
            require_client(usuario)

    assert error.value.status_code == 403


def test_require_client_acepta_a_un_cliente(client: TestClient) -> None:
    """Un cliente autenticado atraviesa la restricción de rol."""
    cuenta = register_user(client, "ana@example.com")

    with SessionLocal() as session:
        usuario = resolve_current_user(
            session, create_access_token(user_id=cuenta["id"], role="client")
        )
        assert require_client(usuario).id == cuenta["id"]


def test_un_veterinario_registrado_puede_iniciar_sesion_y_resolver_su_cuenta(
    client: TestClient,
) -> None:
    """El token de un veterinario lleva su rol y resuelve su propia cuenta."""
    cuenta = register_user(client, "dra.solis@example.com", role="vet")

    token = login(client, "dra.solis@example.com")
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    assert payload["role"] == "vet"

    with SessionLocal() as session:
        usuario = resolve_current_user(session, token)
        assert usuario.id == cuenta["id"]
        assert usuario.role == "vet"


def test_un_cliente_registrado_puede_iniciar_sesion_y_resolver_su_cuenta(
    client: TestClient,
) -> None:
    """El token de un cliente lleva su rol y resuelve su propia cuenta."""
    cuenta = register_user(client, "ana@example.com", role="client")

    token = login(client, "ana@example.com")
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    assert payload["role"] == "client"

    with SessionLocal() as session:
        usuario = resolve_current_user(session, token)
        assert usuario.id == cuenta["id"]
        assert usuario.role == "client"


def test_el_token_emitido_permite_usar_la_cabecera_bearer(client: TestClient) -> None:
    """La cabecera construida con el token emitido es la que espera la API."""
    register_user(client, "ana@example.com")

    cabecera = auth_header(login(client, "ana@example.com"))

    assert cabecera["Authorization"].startswith("Bearer ")


@pytest.mark.parametrize("method,path,body", ENDPOINTS_PROTEGIDOS)
def test_los_endpoints_protegidos_responden_401_sin_token(
    client: TestClient, method: str, path: str, body: dict | None
) -> None:
    """Cada endpoint protegido rechaza la petición sin cabecera Authorization."""
    response = _request(client, method, path, body)

    assert response.status_code == 401


@pytest.mark.parametrize("method,path,body", ENDPOINTS_PROTEGIDOS)
@pytest.mark.parametrize("cabecera", CABECERAS_MAL_FORMADAS)
def test_los_endpoints_protegidos_responden_401_con_cabecera_mal_formada(
    client: TestClient,
    method: str,
    path: str,
    body: dict | None,
    cabecera: dict[str, str],
) -> None:
    """Una cabecera Authorization mal formada no habilita el acceso."""
    response = _request(client, method, path, body, headers=cabecera)

    assert response.status_code == 401


@pytest.mark.parametrize("method,path,body", ENDPOINTS_PROTEGIDOS)
def test_los_endpoints_protegidos_responden_401_con_token_invalido(
    client: TestClient, method: str, path: str, body: dict | None
) -> None:
    """Un token que no es válido no habilita el acceso."""
    response = _request(
        client,
        method,
        path,
        body,
        headers={"Authorization": "Bearer un.token.invalido"},
    )

    assert response.status_code == 401


def test_los_endpoints_publicos_siguen_siendo_accesibles(client: TestClient) -> None:
    """Health, registro e inicio de sesión se pueden usar sin token."""
    salud = client.get("/health")
    registro = client.post(
        "/auth/register",
        json={
            "email": "ana@example.com",
            "password": DEFAULT_PASSWORD,
            "role": "client",
        },
    )
    inicio_de_sesion = client.post(
        "/auth/login", json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    )

    assert salud.status_code == 200
    assert salud.json() == {"status": "ok"}
    assert registro.status_code == 201
    assert inicio_de_sesion.status_code == 200
    assert inicio_de_sesion.json()["token_type"] == "bearer"
