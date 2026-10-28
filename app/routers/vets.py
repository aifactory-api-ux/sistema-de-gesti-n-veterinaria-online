"""Endpoint de consulta del directorio de veterinarios."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import VetPublic

router = APIRouter(tags=["veterinarios"])


@router.get(
    "/vets",
    response_model=list[VetPublic],
    summary="Lista los veterinarios disponibles",
)
def listar_veterinarios(
    db: Annotated[Session, Depends(get_db)],
    usuario: Annotated[User, Depends(get_current_user)],
) -> list[User]:
    """Devuelve los veterinarios registrados como una lista de `{id, email}`.

    Solo se incluyen los usuarios con rol `vet`: los clientes no aparecen en
    el directorio. La dependencia `get_current_user` exige un token Bearer
    válido, de modo que sin cabecera o con un token inválido la API responde
    `401` antes de llegar al manejador.
    """
    return list(
        db.scalars(select(User).where(User.role == "vet").order_by(User.id)).all()
    )
