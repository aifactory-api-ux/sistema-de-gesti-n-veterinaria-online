"""Endpoints públicos de registro e inicio de sesión."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import (
    MENSAJE_CREDENCIALES,
    MENSAJE_EMAIL_DUPLICADO,
    conflict,
    unauthorized,
)
from app.models import User
from app.schemas import Token, UserCreate, UserLogin, UserPublic
from app.security import emitir_token, hashear_password, verificar_password

router = APIRouter(prefix="/auth", tags=["autenticación"])


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Registra un cliente o un veterinario",
)
def registrar_usuario(
    datos: UserCreate,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Crea un usuario nuevo y devuelve únicamente sus datos públicos.

    Responde `409` si el email ya está registrado y `422` si la contraseña
    tiene menos de ocho caracteres o el rol no es `client` ni `vet`.
    """
    existente = db.scalar(select(User).where(User.email == datos.email))
    if existente is not None:
        raise conflict(MENSAJE_EMAIL_DUPLICADO)

    usuario = User(
        email=datos.email,
        password_hash=hashear_password(datos.password),
        role=datos.role,
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        # El índice único de `users.email` es la red de seguridad ante una
        # carrera entre la comprobación previa y la inserción.
        db.rollback()
        raise conflict(MENSAJE_EMAIL_DUPLICADO) from None
    db.refresh(usuario)

    return usuario


@router.post(
    "/login",
    response_model=Token,
    summary="Inicia sesión y devuelve un token de acceso",
)
def iniciar_sesion(
    datos: UserLogin,
    db: Annotated[Session, Depends(get_db)],
) -> Token:
    """Verifica las credenciales y emite un JWT de acceso.

    Responde `401` con el mismo mensaje si el email no existe o si la
    contraseña no coincide, sin revelar cuál de los dos datos falló.
    """
    usuario = db.scalar(select(User).where(User.email == datos.email))
    if usuario is None or not verificar_password(datos.password, usuario.password_hash):
        raise unauthorized(MENSAJE_CREDENCIALES)

    return Token(
        access_token=emitir_token(usuario.id, usuario.role),
        token_type="bearer",
    )
