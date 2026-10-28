"""Pruebas del endpoint de estado del servicio."""

from fastapi.testclient import TestClient


def test_health_responde_ok_sin_credenciales(client: TestClient) -> None:
    """El endpoint es público y devuelve el cuerpo exacto esperado."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_responde_ok_con_un_token_invalido(client: TestClient) -> None:
    """Un token inválido no bloquea el chequeo de estado."""
    response = client.get("/health", headers={"Authorization": "Bearer token.inventado"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
