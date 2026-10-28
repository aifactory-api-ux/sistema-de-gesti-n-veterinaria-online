"""Pruebas del registro y el listado de mascotas."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from tests.conftest import auth_header, login, register_user


def _utc_today() -> str:
    """Devuelve la fecha actual en UTC con formato ISO 8601."""
    return datetime.now(timezone.utc).date().isoformat()


def _utc_tomorrow() -> str:
    """Devuelve la fecha de mañana en UTC con formato ISO 8601."""
    return (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()


def _pet_payload(**overrides: str) -> dict:
    """Construye el cuerpo de alta de una mascota con los datos indicados."""
    payload = {"name": "Firulais", "species": "dog", "birth_date": "2021-03-15"}
    payload.update(overrides)
    return payload


def test_alta_de_mascota_sin_token_responde_401(client: TestClient) -> None:
    """El registro de mascotas exige un token bearer válido."""
    response = client.post("/pets", json=_pet_payload())

    assert response.status_code == 401


def test_listado_de_mascotas_sin_token_responde_401(client: TestClient) -> None:
    """El listado de mascotas exige un token bearer válido."""
    response = client.get("/pets")

    assert response.status_code == 401


def test_cliente_registra_una_mascota(client: TestClient) -> None:
    """El alta responde 201 con los datos de la mascota y su propietario."""
    cliente = register_user(client, "ana@example.com")

    response = client.post(
        "/pets",
        json=_pet_payload(),
        headers=auth_header(login(client, "ana@example.com")),
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "name", "species", "birth_date", "owner_id"}
    assert isinstance(body["id"], int)
    assert body["name"] == "Firulais"
    assert body["species"] == "dog"
    assert body["birth_date"] == "2021-03-15"
    assert body["owner_id"] == cliente["id"]


def test_veterinario_no_puede_registrar_mascotas(client: TestClient) -> None:
    """Un veterinario recibe 403 y la mascota no queda registrada."""
    register_user(client, "dra.solis@example.com", role="vet")

    response = client.post(
        "/pets",
        json=_pet_payload(),
        headers=auth_header(login(client, "dra.solis@example.com")),
    )

    assert response.status_code == 403
    listado = client.get(
        "/pets", headers=auth_header(login(client, "dra.solis@example.com"))
    )
    assert listado.json() == []


def test_especie_fuera_del_vocabulario_responde_422(client: TestClient) -> None:
    """Una especie distinta de dog, cat y other se rechaza y no se registra."""
    register_user(client, "ana@example.com")

    response = client.post(
        "/pets",
        json=_pet_payload(species="hamster"),
        headers=auth_header(login(client, "ana@example.com")),
    )

    assert response.status_code == 422
    listado = client.get(
        "/pets", headers=auth_header(login(client, "ana@example.com"))
    )
    assert listado.json() == []


def test_especie_other_se_acepta(client: TestClient) -> None:
    """La especie `other` pertenece al vocabulario y se registra."""
    register_user(client, "ana@example.com")

    response = client.post(
        "/pets",
        json=_pet_payload(species="other"),
        headers=auth_header(login(client, "ana@example.com")),
    )

    assert response.status_code == 201
    assert response.json()["species"] == "other"


def test_fecha_de_nacimiento_futura_responde_422(client: TestClient) -> None:
    """Una mascota nacida mañana se rechaza y no se registra."""
    register_user(client, "ana@example.com")

    response = client.post(
        "/pets",
        json=_pet_payload(birth_date=_utc_tomorrow()),
        headers=auth_header(login(client, "ana@example.com")),
    )

    assert response.status_code == 422
    listado = client.get(
        "/pets", headers=auth_header(login(client, "ana@example.com"))
    )
    assert listado.json() == []


def test_mascota_nacida_hoy_se_acepta(client: TestClient) -> None:
    """Una mascota nacida el día actual es válida."""
    register_user(client, "ana@example.com")

    response = client.post(
        "/pets",
        json=_pet_payload(birth_date=_utc_today()),
        headers=auth_header(login(client, "ana@example.com")),
    )

    assert response.status_code == 201
    assert response.json()["birth_date"] == _utc_today()


def test_listado_muestra_solo_las_mascotas_del_cliente(client: TestClient) -> None:
    """Cada cliente ve únicamente las mascotas que registró."""
    register_user(client, "ana@example.com")
    register_user(client, "bruno@example.com")
    token_ana = login(client, "ana@example.com")
    token_bruno = login(client, "bruno@example.com")

    creada_por_ana = client.post(
        "/pets", json=_pet_payload(name="Firulais"), headers=auth_header(token_ana)
    )
    creada_por_bruno = client.post(
        "/pets", json=_pet_payload(name="Roco"), headers=auth_header(token_bruno)
    )

    assert creada_por_ana.status_code == 201
    assert creada_por_bruno.status_code == 201
    listado = client.get("/pets", headers=auth_header(token_ana))

    assert listado.status_code == 200
    body = listado.json()
    assert [pet["name"] for pet in body] == ["Firulais"]
    assert body[0]["id"] == creada_por_ana.json()["id"]


def test_veterinario_no_ve_mascotas_de_los_clientes(client: TestClient) -> None:
    """El listado de un veterinario no expone las mascotas de otros."""
    register_user(client, "ana@example.com")
    register_user(client, "dra.solis@example.com", role="vet")
    token_ana = login(client, "ana@example.com")
    token_vet = login(client, "dra.solis@example.com")
    client.post("/pets", json=_pet_payload(), headers=auth_header(token_ana))

    response = client.get("/pets", headers=auth_header(token_vet))

    assert response.status_code == 200
    assert response.json() == []


def test_listado_sin_mascotas_responde_200_con_lista_vacia(
    client: TestClient,
) -> None:
    """Un cliente sin mascotas registradas recibe un arreglo vacío."""
    register_user(client, "ana@example.com")

    response = client.get(
        "/pets", headers=auth_header(login(client, "ana@example.com"))
    )

    assert response.status_code == 200
    assert response.json() == []
