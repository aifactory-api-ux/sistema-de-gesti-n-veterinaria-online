"""Motor de base de datos, fábrica de sesiones y dependencia de sesión."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    """Base declarativa común a todas las tablas del proyecto."""


def _engine_options(url: str) -> dict:
    """Ajusta las opciones del motor según el backend de la URL."""
    options: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url or url in ("sqlite://", "sqlite:///"):
            # Una base en memoria solo existe mientras vive su conexión: se reutiliza una sola.
            options["poolclass"] = StaticPool
    return options


settings = get_settings()
engine: Engine = create_engine(
    settings.database_url, **_engine_options(settings.database_url)
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Entrega una sesión por petición y la cierra al terminar."""
    with SessionLocal() as session:
        yield session
