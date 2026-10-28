"""Directorio de veterinarios de la clínica."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import VetResponse

router = APIRouter(prefix="/vets", tags=["vets"])


@router.get("", response_model=list[VetResponse])
def list_vets(
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[User]:
    """Devuelve las cuentas con rol de veterinario.

    La dependencia exige un token válido aunque el listado no dependa del rol
    de quien consulta.
    """
    return list(db.scalars(select(User).where(User.role == "vet").order_by(User.id)))
