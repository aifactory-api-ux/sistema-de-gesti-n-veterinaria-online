"""Endpoint de estado del servicio."""

from fastapi import APIRouter

from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Responde con el estado del servicio, sin requerir credenciales."""
    return HealthResponse(status="ok")
