"""Pruebas unitarias del hash de contraseñas y de los tokens JWT."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings
from app.security import (
    decodificar_token,
    emitir_token,
    hashear_password,
    verificar_password,
)

CONTRASENA = "secreto123"


def test_dos_contrasenas_iguales_producen_hashes_distintos() -> None:
    """El hash usa sal aleatoria, de modo que nunca se repite."""
    primero = hashear_password(CONTRASENA)
    segundo = hashear_password(CONTRASENA)

    assert primero != segundo


def test_el_hash_usa_argon2_y_no_contiene_la_contrasena() -> None:
    hash_calculado = hashear_password(CONTRASENA)

    assert hash_calculado.startswith("$argon2")
    assert CONTRASENA not in hash_calculado


def test_verificar_password_acepta_la_contrasena_correcta() -> None:
    hash_calculado = hashear_password(CONTRASENA)

    assert verificar_password(CONTRASENA, hash_calculado) is True


def test_verificar_password_rechaza_una_contrasena_distinta() -> None:
    hash_calculado = hashear_password(CONTRASENA)

    assert verificar_password("otraClave9", hash_calculado) is False


def test_el_token_emitido_lleva_el_sub_y_el_role_esperados() -> None:
    token = emitir_token(7, "vet")

    claims = decodificar_token(token)

    assert claims["sub"] == "7"
    assert claims["role"] == "vet"


def test_el_token_emitido_lleva_iat_y_exp() -> None:
    token = emitir_token(7, "client")

    claims = decodificar_token(token)

    assert claims["iat"] <= claims["exp"]
    assert claims["exp"] - claims["iat"] == settings.JWT_EXPIRE_MINUTES * 60


def test_un_token_firmado_con_otro_secreto_no_se_decodifica() -> None:
    token = jwt.encode(
        {"sub": "7", "role": "client", "iat": 0, "exp": 4_102_444_800},
        "un-secreto-distinto-de-pruebas-para-el-token-jwt",
        algorithm=settings.JWT_ALGORITHM,
    )

    with pytest.raises(jwt.InvalidSignatureError):
        decodificar_token(token)


def test_un_token_expirado_no_se_decodifica() -> None:
    ahora = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "7",
            "role": "client",
            "iat": int((ahora - timedelta(hours=2)).timestamp()),
            "exp": int((ahora - timedelta(hours=1)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decodificar_token(token)


def test_un_token_sin_claims_obligatorios_no_se_decodifica() -> None:
    token = jwt.encode(
        {"sub": "7"},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    with pytest.raises(jwt.MissingRequiredClaimError):
        decodificar_token(token)
