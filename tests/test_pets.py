"""Pruebas del registro y del listado de mascotas."""

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Pet
from app.schemas import validar_nacimiento_no_futuro

CONTRASENA = "secreto123"
EMAIL_CLIENTE = "ana@example.com"
EMAIL_OTRO_CLIENTE = "bruno@example.com"
EMAIL_VETERINARIO = "dra.luz@example.com"

ESPECIES_ADMITIDAS = ("dog", "cat", "other")


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


def _cliente_autenticado(
    client: TestClient, email: str = EMAIL_CLIENTE
) -> tuple[dict, str]:
    """Registra un cliente, inicia sesión y devuelve su cuerpo y su token."""
    cuerpo = _registrar(client, email, "client")
    return cuerpo, _token(client, email)


def _total_de_mascotas(sesion_local: sessionmaker[Session]) -> int:
    """Cuenta las mascotas almacenadas en la base de pruebas."""
    with sesion_local() as sesion:
        return sesion.scalar(select(func.count()).select_from(Pet)) or 0


def _fecha_actual_de_la_api() -> date:
    """Devuelve la fecha que la aplicación considera el día actual.

    La fecha se delega en el validador de la API (`validar_nacimiento_no_futuro`),
    que compara con el día en UTC. Así la prueba usa exactamente la misma zona
    horaria que la aplicación y no depende de la hora local del equipo: un
    cambio de día en UTC durante la prueba no invalida el caso, porque la fecha
    derivada nunca queda en el futuro respecto del instante de la petición.
    """
    return validar_nacimiento_no_futuro(datetime.now(timezone.utc).date())


# --- Alta de mascotas --------------------------------------------------------


def test_alta_de_mascota_responde_201_con_todos_los_campos(
    client: TestClient,
) -> None:
    cliente, token = _cliente_autenticado(client)

    respuesta = client.post(
        "/pets",
        json={"name": "Firulais", "species": "dog", "birth_date": "2020-05-04"},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"id", "name", "species", "birth_date", "owner_id"}
    assert cuerpo["name"] == "Firulais"
    assert cuerpo["species"] == "dog"
    assert cuerpo["birth_date"] == "2020-05-04"
    assert cuerpo["owner_id"] == cliente["id"]
    assert isinstance(cuerpo["id"], int)


def test_la_mascota_se_guarda_con_el_cliente_autenticado_como_propietario(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    cliente, token = _cliente_autenticado(client)

    respuesta = client.post(
        "/pets",
        json={"name": "Luna", "species": "cat", "birth_date": "2021-08-15"},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 201
    with sesion_local() as sesion:
        mascota = sesion.scalar(select(Pet).where(Pet.name == "Luna"))
    assert mascota is not None
    assert mascota.owner_id == cliente["id"]


def test_el_propietario_no_puede_elegirse_en_el_cuerpo(
    client: TestClient,
) -> None:
    cliente, token = _cliente_autenticado(client)
    otro, _ = _cliente_autenticado(client, EMAIL_OTRO_CLIENTE)

    respuesta = client.post(
        "/pets",
        json={
            "name": "Rayo",
            "species": "dog",
            "birth_date": "2022-02-02",
            "owner_id": otro["id"],
        },
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["owner_id"] == cliente["id"]


@pytest.mark.parametrize("especie", ESPECIES_ADMITIDAS)
def test_las_especies_admitidas_registran_la_mascota(
    client: TestClient, especie: str
) -> None:
    _, token = _cliente_autenticado(client)

    respuesta = client.post(
        "/pets",
        json={"name": "Paco", "species": especie, "birth_date": "2021-01-01"},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["species"] == especie


def test_una_especie_no_admitida_responde_422_y_no_registra(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _, token = _cliente_autenticado(client)

    respuesta = client.post(
        "/pets",
        json={"name": "Paco", "species": "hamster", "birth_date": "2021-01-01"},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 422
    assert _total_de_mascotas(sesion_local) == 0


def test_una_fecha_de_nacimiento_futura_responde_422_y_no_registra(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _, token = _cliente_autenticado(client)

    respuesta = client.post(
        "/pets",
        json={"name": "Futura", "species": "cat", "birth_date": "2999-01-01"},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 422
    assert _total_de_mascotas(sesion_local) == 0


def test_una_fecha_de_nacimiento_igual_al_dia_actual_responde_201(
    client: TestClient,
) -> None:
    _, token = _cliente_autenticado(client)
    hoy = _fecha_actual_de_la_api().isoformat()

    respuesta = client.post(
        "/pets",
        json={"name": "Hoy", "species": "cat", "birth_date": hoy},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["birth_date"] == hoy


def test_el_veterinario_no_puede_registrar_mascotas(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _registrar(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_VETERINARIO)

    respuesta = client.post(
        "/pets",
        json={"name": "Rayo", "species": "dog", "birth_date": "2022-02-02"},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 403
    assert _total_de_mascotas(sesion_local) == 0


def test_el_alta_sin_token_responde_401(client: TestClient) -> None:
    respuesta = client.post(
        "/pets",
        json={"name": "Firulais", "species": "dog", "birth_date": "2020-05-04"},
    )

    assert respuesta.status_code == 401
    assert "detail" in respuesta.json()


def test_el_alta_con_token_invalido_responde_401(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    respuesta = client.post(
        "/pets",
        json={"name": "Firulais", "species": "dog", "birth_date": "2020-05-04"},
        headers={"Authorization": "Bearer token.inventado.aaa"},
    )

    assert respuesta.status_code == 401
    assert _total_de_mascotas(sesion_local) == 0


# --- Listado de mascotas -----------------------------------------------------


def test_el_listado_devuelve_solo_las_mascotas_propias(client: TestClient) -> None:
    cliente, token_cliente = _cliente_autenticado(client)
    _, token_otro = _cliente_autenticado(client, EMAIL_OTRO_CLIENTE)

    for nombre in ("Firulais", "Luna"):
        respuesta = client.post(
            "/pets",
            json={"name": nombre, "species": "dog", "birth_date": "2020-05-04"},
            headers=_cabecera(token_cliente),
        )
        assert respuesta.status_code == 201
    respuesta = client.post(
        "/pets",
        json={"name": "Rayo", "species": "cat", "birth_date": "2021-03-03"},
        headers=_cabecera(token_otro),
    )
    assert respuesta.status_code == 201

    respuesta = client.get("/pets", headers=_cabecera(token_cliente))

    assert respuesta.status_code == 200
    mascotas = respuesta.json()
    assert {mascota["name"] for mascota in mascotas} == {"Firulais", "Luna"}
    assert {mascota["owner_id"] for mascota in mascotas} == {cliente["id"]}


def test_el_listado_de_un_cliente_sin_mascotas_devuelve_un_arreglo_vacio(
    client: TestClient,
) -> None:
    _, token = _cliente_autenticado(client, EMAIL_OTRO_CLIENTE)

    respuesta = client.get("/pets", headers=_cabecera(token))

    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_el_listado_sin_token_responde_401(client: TestClient) -> None:
    respuesta = client.get("/pets")

    assert respuesta.status_code == 401
    assert "detail" in respuesta.json()


def test_el_listado_con_token_invalido_responde_401(client: TestClient) -> None:
    respuesta = client.get(
        "/pets", headers={"Authorization": "Bearer token.inventado.aaa"}
    )

    assert respuesta.status_code == 401


def test_el_veterinario_no_ve_las_mascotas_de_los_clientes(
    client: TestClient,
) -> None:
    _, token_cliente = _cliente_autenticado(client)
    _registrar(client, EMAIL_VETERINARIO, "vet")
    token_vet = _token(client, EMAIL_VETERINARIO)
    respuesta = client.post(
        "/pets",
        json={"name": "Firulais", "species": "dog", "birth_date": "2020-05-04"},
        headers=_cabecera(token_cliente),
    )
    assert respuesta.status_code == 201

    respuesta = client.get("/pets", headers=_cabecera(token_vet))

    assert respuesta.status_code == 200
    assert respuesta.json() == []
