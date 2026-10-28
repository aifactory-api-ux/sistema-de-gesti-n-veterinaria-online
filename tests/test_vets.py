"""Pruebas del directorio de veterinarios."""

from fastapi.testclient import TestClient

from tests.conftest import auth_header, login, register_user


def test_directorio_sin_token_responde_401(client: TestClient) -> None:
    """El directorio exige un token bearer válido."""
    response = client.get("/vets")

    assert response.status_code == 401


def test_directorio_con_token_invalido_responde_401(client: TestClient) -> None:
    """Un token que no corresponde a ninguna cuenta es rechazado."""
    response = client.get("/vets", headers=auth_header("token.inventado"))

    assert response.status_code == 401


def test_directorio_lista_a_los_veterinarios(client: TestClient) -> None:
    """Cada veterinario registrado aparece con su identificador y su correo."""
    register_user(client, "dra.solis@example.com", role="vet")
    register_user(client, "dra.ramos@example.com", role="vet")

    cliente = register_user(client, "ana@example.com")
    response = client.get("/vets", headers=auth_header(login(client, "ana@example.com")))

    assert response.status_code == 200
    body = response.json()
    assert [entry["email"] for entry in body] == [
        "dra.solis@example.com",
        "dra.ramos@example.com",
    ]
    assert all(isinstance(entry["id"], int) for entry in body)
    assert cliente["id"] not in [entry["id"] for entry in body]


def test_directorio_no_expone_otros_datos_de_la_cuenta(client: TestClient) -> None:
    """Las entradas del directorio solo contienen el identificador y el correo."""
    register_user(client, "dra.solis@example.com", role="vet")
    register_user(client, "ana@example.com")

    response = client.get("/vets", headers=auth_header(login(client, "ana@example.com")))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert set(body[0]) == {"id", "email"}
    assert body[0]["email"] == "dra.solis@example.com"


def test_directorio_vacio_responde_200_con_lista_vacia(client: TestClient) -> None:
    """Sin veterinarios registrados el directorio responde con un arreglo vacío."""
    register_user(client, "ana@example.com")

    response = client.get("/vets", headers=auth_header(login(client, "ana@example.com")))

    assert response.status_code == 200
    assert response.json() == []


def test_un_veterinario_también_puede_consultar_el_directorio(
    client: TestClient,
) -> None:
    """Cualquier cuenta autenticada, incluida la de un veterinario, lista el directorio."""
    register_user(client, "dra.solis@example.com", role="vet")

    response = client.get(
        "/vets", headers=auth_header(login(client, "dra.solis@example.com"))
    )

    assert response.status_code == 200
    assert [entry["email"] for entry in response.json()] == ["dra.solis@example.com"]
