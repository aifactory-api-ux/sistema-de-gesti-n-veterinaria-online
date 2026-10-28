"""Dependencias de autenticación y autorización de la API."""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    description="Token de acceso emitido por POST /auth/login",
)

INVALID_CREDENTIALS = "Credenciales de autenticación ausentes o inválidas"
CLIENT_ONLY_REQUIRED = "La operación requiere una cuenta de cliente"


def _unauthorized() -> HTTPException:
    """Construye el error 401 con el encabezado de negociación del esquema."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=INVALID_CREDENTIALS,
        headers={"WWW-Authenticate": "Bearer"},
    )


def resolve_current_user(db: Session, token: str) -> User:
    """Resuelve la cuenta a partir de un token bearer.

    Lanza 401 si el token no es válido, ha expirado o no corresponde a una
    cuenta existente.
    """
    try:
        payload = decode_access_token(token)
    except jwt.InvalidTokenError as error:
        raise _unauthorized() from error

    subject = payload.get("sub")
    try:
        user_id = int(subject)
    except (TypeError, ValueError) as error:
        raise _unauthorized() from error

    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized()
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Entrega la cuenta autenticada de la petición."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized()
    return resolve_current_user(db, credentials.credentials)


def require_client(current_user: User = Depends(get_current_user)) -> User:
    """Entrega la cuenta autenticada solo si pertenece a un cliente."""
    if current_user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=CLIENT_ONLY_REQUIRED
        )
    return current_user
