"""Endpoints de alta y listado de las mascotas del cliente autenticado."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_client
from app.models import Pet, User
from app.schemas import PetCreate, PetPublic

router = APIRouter(tags=["mascotas"])


@router.post(
    "/pets",
    response_model=PetPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Registra una mascota a nombre del cliente autenticado",
)
def registrar_mascota(
    datos: PetCreate,
    db: Annotated[Session, Depends(get_db)],
    usuario: Annotated[User, Depends(require_client)],
) -> Pet:
    """Crea una mascota del cliente autenticado y devuelve sus datos.

    El propietario se toma siempre del token: un cliente no puede registrar
    una mascota a nombre de otro. La dependencia `require_client` responde
    `403` cuando el portador del token tiene rol `vet`, y la validación del
    cuerpo produce `422` ante una especie no admitida o una fecha de
    nacimiento futura.
    """
    mascota = Pet(
        name=datos.name,
        species=datos.species,
        birth_date=datos.birth_date,
        owner_id=usuario.id,
    )
    db.add(mascota)
    db.commit()
    db.refresh(mascota)

    return mascota


@router.get(
    "/pets",
    response_model=list[PetPublic],
    summary="Lista las mascotas del usuario autenticado",
)
def listar_mascotas(
    db: Annotated[Session, Depends(get_db)],
    usuario: Annotated[User, Depends(get_current_user)],
) -> list[Pet]:
    """Devuelve únicamente las mascotas cuyo propietario es el usuario autenticado.

    La dependencia `get_current_user` exige un token Bearer válido, de modo que
    sin cabecera o con un token inválido la API responde `401` antes de llegar
    al manejador.
    """
    return list(
        db.scalars(select(Pet).where(Pet.owner_id == usuario.id).order_by(Pet.id)).all()
    )
