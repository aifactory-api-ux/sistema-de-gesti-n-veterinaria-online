"""Hash de contraseñas y emisión y decodificación de tokens JWT.

Las contraseñas se guardan con Argon2 y sal aleatoria por usuario: el material
original nunca se almacena ni se devuelve. Los tokens son JWT firmados con el
algoritmo y el secreto configurados en el entorno, y llevan los claims `sub`
(id del usuario), `role`, `iat` (emisión) y `exp` (caducidad).
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.config import settings

# Argon2 con sal aleatoria en cada hash: dos contraseñas iguales nunca coinciden.
hashador = PasswordHash((Argon2Hasher(),))

# Claims que todo token emitido por la API debe incluir.
CLAIMS_REQUERIDOS = ("sub", "role", "iat", "exp")


def hashear_password(password: str) -> str:
    """Devuelve el hash Argon2 con sal aleatoria de una contraseña en claro."""
    return hashador.hash(password)


def verificar_password(password: str, password_hash: str) -> bool:
    """Indica si una contraseña en claro corresponde al hash almacenado."""
    return hashador.verify(password, password_hash)


def emitir_token(usuario_id: int, rol: str) -> str:
    """Emite un JWT firmado con los claims `sub`, `role`, `iat` y `exp`."""
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario_id),
        "role": rol,
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decodificar_token(token: str) -> dict[str, Any]:
    """Decodifica y valida un JWT emitido por la API.

    Lanza `jwt.InvalidTokenError` (o `jwt.ExpiredSignatureError`) si el token
    está mal formado, tiene una firma inválida, ha expirado o le falta alguno de
    los claims obligatorios.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": list(CLAIMS_REQUERIDOS)},
    )
