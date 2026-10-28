"""Pruebas del directorio de veterinarios."""

from fastapi.testclient import TestClient

CONTRASENA = "secreto123"
EMAIL_VET_1 = "dra.luz@example.com"
EMAIL_VET_2 = "dr.carlos@example.com"
EMAIL_CLIENTE = "ana@example.com"


def _registrar(client: TestClient, email: str, rol: str) -> dict:
    """Registra un usuario mediante la API y devuelve el cuerpo de la respuesta."""
    respuesta = client.post(
        "/auth/register",
        json={"email": email, "password": CONTRASENA, "role": rol},
    )
    assert respuesta.status_code == 201
    return respuesta.json()


def _token(client: TestClient, email: str) -> str:
    """Inicia sesión y devuelve el token de acceso del usuario indicado."""
    respuesta = client.post(
        "/auth/login", json={"email": email, "password": CONTRASENA}
    )
    assert respuesta.status_code == 200
    return respuesta.json()["access_token"]


def _cabecera(token: str) -> dict[str, str]:
    """Construye la cabecera `Authorization: Bearer` con el token indicado."""
    return {"Authorization": f"Bearer {token}"}


# --- Listado del directorio -------------------------------------------------


def test_directorio_lista_solo_los_veterinarios(client: TestClient) -> None:
    luz = _registrar(client, EMAIL_VET_1, "vet")
    carlos = _registrar(client, EMAIL_VET_2, "vet")
    _registrar(client, EMAIL_CLIENTE, "client")

    respuesta = client.get("/vets", headers=_cabecera(_token(client, EMAIL_CLIENTE)))

    assert respuesta.status_code == 200
    directorio = respuesta.json()
    assert {vet["email"] for vet in directorio} == {EMAIL_VET_1, EMAIL_VET_2}
    assert {vet["id"] for vet in directorio} == {luz["id"], carlos["id"]}
    assert len(directorio) == 2


def test_cada_elemento_del_directorio_solo_tiene_id_y_email(
    client: TestClient,
) -> None:
    _registrar(client, EMAIL_VET_1, "vet")

    respuesta = client.get("/vets", headers=_cabecera(_token(client, EMAIL_VET_1)))

    assert respuesta.status_code == 200
    directorio = respuesta.json()
    assert len(directorio) == 1
    assert set(directorio[0]) == {"id", "email"}
    assert isinstance(directorio[0]["id"], int)


def test_los_clientes_no_aparecen_en_el_directorio(client: TestClient) -> None:
    _registrar(client, EMAIL_CLIENTE, "client")
    _registrar(client, EMAIL_VET_1, "vet")

    respuesta = client.get("/vets", headers=_cabecera(_token(client, EMAIL_CLIENTE)))

    assert respuesta.status_code == 200
    emails = [vet["email"] for vet in respuesta.json()]
    assert EMAIL_CLIENTE not in emails
    assert emails == [EMAIL_VET_1]


def test_directorio_sin_veterinarios_devuelve_arreglo_vacio(
    client: TestClient,
) -> None:
    _registrar(client, EMAIL_CLIENTE, "client")

    respuesta = client.get("/vets", headers=_cabecera(_token(client, EMAIL_CLIENTE)))

    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_el_directorio_tambien_se_consulta_con_el_token_de_un_veterinario(
    client: TestClient,
) -> None:
    _registrar(client, EMAIL_VET_1, "vet")

    respuesta = client.get("/vets", headers=_cabecera(_token(client, EMAIL_VET_1)))

    assert respuesta.status_code == 200
    assert [vet["email"] for vet in respuesta.json()] == [EMAIL_VET_1]


# --- Exigencia de autenticación ---------------------------------------------


def test_directorio_sin_token_responde_401(client: TestClient) -> None:
    respuesta = client.get("/vets")

    assert respuesta.status_code == 401
    assert "detail" in respuesta.json()


def test_directorio_con_token_invalido_responde_401(client: TestClient) -> None:
    respuesta = client.get("/vets", headers={"Authorization": "Bearer token.inventado.aaa"})

    assert respuesta.status_code == 401


def test_directorio_con_esquema_distinto_de_bearer_responde_401(
    client: TestClient,
) -> None:
    respuesta = client.get("/vets", headers={"Authorization": "Basic dXNlcjpwYXNz"})

    assert respuesta.status_code == 401
