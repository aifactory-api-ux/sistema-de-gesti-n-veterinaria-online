"""Endpoint público de salud de la API."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["salud"])


class HealthResponse(BaseModel):
    """Cuerpo de la respuesta del endpoint de salud.

    Solo expone el estado del servicio: ni información de la base de datos
    ni datos de usuarios.
    """

    status: Literal["ok"] = "ok"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Comprueba que la API está operativa",
)
def health() -> HealthResponse:
    """Responde `200` con el cuerpo `{"status": "ok"}` sin exigir credenciales."""
    return HealthResponse(status="ok")
