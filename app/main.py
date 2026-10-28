"""Aplicación FastAPI de la clínica veterinaria."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.routers import appointments, auth, health, pets, vets


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Crea el esquema de la base de datos al arrancar la aplicación."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="API de la clínica veterinaria",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(vets.router)
app.include_router(pets.router)
app.include_router(appointments.router)
