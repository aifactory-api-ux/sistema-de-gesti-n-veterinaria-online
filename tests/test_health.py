"""Pruebas del endpoint público de salud."""

from fastapi.testclient import TestClient


def test_health_responde_ok_sin_token(client: TestClient) -> None:
    respuesta = client.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_health_responde_ok_con_token_valido(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    respuesta = client.get("/health", headers=auth_headers)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_health_no_expone_datos_de_usuarios_ni_de_base_de_datos(
    client: TestClient,
) -> None:
    cuerpo = client.get("/health").json()

    assert set(cuerpo) == {"status"}
    assert cuerpo["status"] == "ok"
