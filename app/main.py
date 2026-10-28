"""Punto de entrada de la API de la clínica veterinaria."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError

from app.database import init_db
from app.dependencies import AutenticacionBearerMiddleware
from app.routers import appointments, auth, health, pets, vets

logger = logging.getLogger(__name__)

INTENTOS_DE_ARRANQUE = 3
ESPERA_ENTRE_INTENTOS_SEGUNDOS = 2.0


async def _preparar_esquema() -> None:
    """Crea el esquema de la base de datos reintentando si aún no responde.

    La API arranca aunque la base de datos no esté disponible: en ese caso se
    registra el error y el endpoint de salud sigue respondiendo para que la
    orquestación pueda observar el estado real del servicio.
    """
    for intento in range(1, INTENTOS_DE_ARRANQUE + 1):
        try:
            init_db()
            return
        except SQLAlchemyError as error:
            logger.warning(
                "Intento %s de preparar el esquema fallido: %s", intento, error
            )
            if intento < INTENTOS_DE_ARRANQUE:
                await asyncio.sleep(ESPERA_ENTRE_INTENTOS_SEGUNDOS)

    logger.error(
        "No se pudo preparar el esquema de la base de datos; la API queda operativa "
        "pero las operaciones que requieren base de datos fallarán."
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Prepara el esquema al arrancar la aplicación."""
    await _preparar_esquema()
    yield


app = FastAPI(
    title="API de la clínica veterinaria",
    description=(
        "API REST para registrar clientes y veterinarios, gestionar las mascotas "
        "de cada cliente y agendar turnos de 30 minutos."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(AutenticacionBearerMiddleware)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(vets.router)
app.include_router(pets.router)
app.include_router(appointments.router)
