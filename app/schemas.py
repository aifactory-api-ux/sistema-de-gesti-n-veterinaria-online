"""Modelos Pydantic de entrada y salida de la API.

Los modelos de entrada validan el cuerpo de las peticiones (por eso un dato
inválido produce `422` de forma nativa) y los modelos de salida fijan las
claves exactas de cada respuesta.
"""

from datetime import date, datetime, timezone
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_serializer,
)

from app.services.scheduling import normalizar_utc

# Únicos roles admitidos en la plataforma.
RolUsuario = Literal["client", "vet"]

# Únicas especies admitidas para una mascota.
EspecieMascota = Literal["dog", "cat", "other"]


def normalizar_email(valor: str) -> str:
    """Normaliza el email a minúsculas para que el registro sea único."""
    return valor.strip().lower()


def validar_nacimiento_no_futuro(valor: date) -> date:
    """Rechaza una fecha de nacimiento posterior a la fecha actual en UTC."""
    if valor > datetime.now(timezone.utc).date():
        raise ValueError("La fecha de nacimiento no puede ser posterior a hoy.")
    return valor


EmailNormalizado = Annotated[EmailStr, BeforeValidator(normalizar_email)]
NacimientoNoFuturo = Annotated[date, AfterValidator(validar_nacimiento_no_futuro)]
NombreMascota = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]
InicioEnUtc = Annotated[datetime, AfterValidator(normalizar_utc)]


class UserCreate(BaseModel):
    """Datos de alta de un usuario de la plataforma."""

    email: EmailNormalizado
    password: str = Field(min_length=8)
    role: RolUsuario


class UserLogin(BaseModel):
    """Credenciales de inicio de sesión de un usuario."""

    email: EmailNormalizado
    password: str


class UserPublic(BaseModel):
    """Datos públicos de un usuario: nunca incluyen material de contraseña."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str


class Token(BaseModel):
    """Token de acceso emitido tras un inicio de sesión correcto."""

    access_token: str
    token_type: str = "bearer"


class VetPublic(BaseModel):
    """Datos públicos de un veterinario del directorio: solo `id` y `email`."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str


class PetCreate(BaseModel):
    """Datos de alta de una mascota.

    El propietario no forma parte del cuerpo: siempre es el cliente
    autenticado que realiza la petición.
    """

    name: NombreMascota
    species: EspecieMascota
    birth_date: NacimientoNoFuturo


class PetPublic(BaseModel):
    """Datos públicos de una mascota registrada."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    species: str
    birth_date: date
    owner_id: int


class AppointmentCreate(BaseModel):
    """Datos de reserva de un turno.

    `start_at` se interpreta siempre en UTC: los instantes sin zona horaria se
    toman como UTC y los que llevan desplazamiento se normalizan a UTC.
    """

    pet_id: int
    vet_id: int
    start_at: InicioEnUtc


class AppointmentPublic(BaseModel):
    """Datos públicos de un turno agendado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    pet_id: int
    vet_id: int
    start_at: datetime
    end_at: datetime
    status: str

    @field_serializer("start_at", "end_at")
    def serializar_en_utc(self, valor: datetime) -> str:
        """Serializa los instantes en ISO 8601 con el desplazamiento UTC."""
        return normalizar_utc(valor).isoformat()
