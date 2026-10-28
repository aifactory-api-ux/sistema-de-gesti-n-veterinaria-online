"""Registro de las mascotas de la clínica."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_client
from app.models import Pet, User
from app.schemas import PetCreate, PetResponse

router = APIRouter(prefix="/pets", tags=["pets"])


@router.post("", response_model=PetResponse, status_code=status.HTTP_201_CREATED)
def create_pet(
    payload: PetCreate,
    owner: User = Depends(require_client),
    db: Session = Depends(get_db),
) -> Pet:
    """Registra una mascota a nombre del cliente autenticado."""
    pet = Pet(
        name=payload.name,
        species=payload.species,
        birth_date=payload.birth_date,
        owner_id=owner.id,
    )
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


@router.get("", response_model=list[PetResponse])
def list_pets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Pet]:
    """Devuelve las mascotas cuyo propietario es la cuenta autenticada."""
    return list(
        db.scalars(
            select(Pet).where(Pet.owner_id == current_user.id).order_by(Pet.id)
        )
    )
