"""Motor, sesión y base declarativa de SQLAlchemy."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base declarativa que agrupa los metadatos de todas las tablas."""


def get_db() -> Generator[Session, None, None]:
    """Entrega una sesión de base de datos por petición y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crea el esquema en la base configurada si todavía no existe.

    La operación es idempotente: solo crea las tablas e índices ausentes.
    """
    from app import models

    models.Base.metadata.create_all(bind=engine)
