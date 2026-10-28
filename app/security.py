"""Hasheo de contraseñas y emisión y verificación de tokens JWT."""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings

ALGORITHM = "HS256"

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Devuelve el hash argon2 de la contraseña, con sal propia."""
    return _password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Indica si la contraseña corresponde al hash almacenado."""
    try:
        return _password_hasher.verify(hashed_password, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(
    user_id: int, role: str, expires_minutes: int | None = None
) -> str:
    """Emite un JWT firmado con el identificador y el rol de la cuenta."""
    settings = get_settings()
    minutes = (
        settings.access_token_expire_minutes
        if expires_minutes is None
        else expires_minutes
    )
    issued_at = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Verifica la firma y la expiración del token y devuelve su contenido.

    Lanza ``jwt.InvalidTokenError`` cuando el token no es válido.
    """
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
