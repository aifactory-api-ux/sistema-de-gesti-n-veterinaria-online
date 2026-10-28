"""Helpers de error con un cuerpo de respuesta uniforme `{"detail": ...}`."""

from fastapi import HTTPException, status

MENSAJE_NO_AUTENTICADO = "Faltan credenciales de autenticación válidas."
MENSAJE_SIN_PERMISOS = "El usuario autenticado no puede realizar esta operación."
MENSAJE_EMAIL_DUPLICADO = "Ya existe un usuario registrado con ese email."
MENSAJE_CREDENCIALES = "El email o la contraseña no son correctos."

CABECERA_BEARER = {"WWW-Authenticate": "Bearer"}

CODIGO_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


def unauthorized(detalle: str = MENSAJE_NO_AUTENTICADO) -> HTTPException:
    """Error 401 para peticiones sin credenciales o con un token inválido."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers=dict(CABECERA_BEARER),
    )


def forbidden(detalle: str = MENSAJE_SIN_PERMISOS) -> HTTPException:
    """Error 403 para peticiones autenticadas sin autorización suficiente."""
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detalle)


def conflict(detalle: str) -> HTTPException:
    """Error 409 para peticiones que chocan con el estado actual del recurso."""
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detalle)


def not_found(detalle: str) -> HTTPException:
    """Error 404 para peticiones sobre recursos que no existen."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detalle)


def unprocessable(detalle: str) -> HTTPException:
    """Error 422 para peticiones cuyo contenido no cumple las reglas del dominio."""
    return HTTPException(status_code=CODIGO_UNPROCESSABLE, detail=detalle)
