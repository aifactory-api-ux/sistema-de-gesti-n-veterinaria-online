"""Autenticación y autorización por token Bearer.

La API es uniforme: todos los endpoints exigen `Authorization: Bearer <token>`
salvo `GET /health`, `POST /auth/register` y `POST /auth/login`. La puerta de
entrada es el middleware `AutenticacionBearerMiddleware`, que valida el token
antes del enrutado, y las dependencias `get_current_user`, `require_client` y
`require_vet` resuelven el usuario autenticado y comprueban su rol.
"""

from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.database import get_db
from app.errors import MENSAJE_NO_AUTENTICADO, forbidden, unauthorized
from app.models import User
from app.security import decodificar_token

# Únicas rutas que se pueden invocar sin credenciales.
RUTAS_PUBLICAS = frozenset({"/health", "/auth/register", "/auth/login"})

esquema_bearer = HTTPBearer(auto_error=False)


def es_ruta_publica(ruta: str) -> bool:
    """Indica si una ruta puede invocarse sin cabecera `Authorization`."""
    return (ruta.rstrip("/") or "/") in RUTAS_PUBLICAS


def _respuesta_no_autenticado() -> JSONResponse:
    """Construye la respuesta `401` con el cuerpo `{"detail": ...}`."""
    return JSONResponse(
        status_code=401,
        content={"detail": MENSAJE_NO_AUTENTICADO},
        headers={"WWW-Authenticate": "Bearer"},
    )


class AutenticacionBearerMiddleware(BaseHTTPMiddleware):
    """Exige un token Bearer válido en todas las rutas que no son públicas.

    La validación se realiza antes del enrutado para que cualquier endpoint
    distinto de los públicos responda `401` cuando falta la cabecera, cuando
    el esquema no es `Bearer` o cuando el token es inválido o ha expirado.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not es_ruta_publica(request.url.path):
            credenciales = await esquema_bearer(request)
            if credenciales is None:
                return _respuesta_no_autenticado()
            try:
                decodificar_token(credenciales.credentials)
            except jwt.InvalidTokenError:
                return _respuesta_no_autenticado()

        return await call_next(request)


def get_current_user(
    credenciales: Annotated[
        HTTPAuthorizationCredentials | None, Depends(esquema_bearer)
    ],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Devuelve el usuario autenticado a partir del token Bearer.

    Responde `401` si falta la cabecera, si el esquema no es `Bearer`, si el
    token es inválido o ha expirado, o si el usuario del token ya no existe.
    """
    if credenciales is None:
        raise unauthorized()

    try:
        claims = decodificar_token(credenciales.credentials)
    except jwt.InvalidTokenError:
        raise unauthorized() from None

    try:
        usuario_id = int(claims["sub"])
    except (KeyError, TypeError, ValueError):
        raise unauthorized() from None

    usuario = db.get(User, usuario_id)
    if usuario is None:
        raise unauthorized()

    return usuario


def require_client(usuario: Annotated[User, Depends(get_current_user)]) -> User:
    """Exige que el usuario autenticado tenga el rol `client`; si no, `403`."""
    if usuario.role != "client":
        raise forbidden()
    return usuario


def require_vet(usuario: Annotated[User, Depends(get_current_user)]) -> User:
    """Exige que el usuario autenticado tenga el rol `vet`; si no, `403`."""
    if usuario.role != "vet":
        raise forbidden()
    return usuario
