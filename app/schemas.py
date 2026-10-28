"""Modelos de entrada y salida de la API."""

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Species = Literal["dog", "cat", "other"]
AppointmentStatus = Literal["scheduled", "cancelled"]


class HealthResponse(BaseModel):
    """Estado del servicio."""

    status: str


class RegisterRequest(BaseModel):
    """Datos necesarios para crear una cuenta."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8)
    role: Literal["client", "vet"]


class LoginRequest(BaseModel):
    """Credenciales de acceso."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """Token de acceso emitido tras un inicio de sesión correcto."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"


class UserResponse(BaseModel):
    """Datos públicos de una cuenta."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str


class VetResponse(BaseModel):
    """Datos publicados de un veterinario en el directorio de la clínica."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str


class PetCreate(BaseModel):
    """Datos de alta de una mascota."""

    name: str = Field(min_length=1, max_length=120)
    species: Species
    birth_date: date

    @field_validator("birth_date")
    @classmethod
    def reject_future_birth_date(cls, value: date) -> date:
        """Impide registrar una mascota con fecha de nacimiento futura."""
        if value > datetime.now(timezone.utc).date():
            raise ValueError("La fecha de nacimiento no puede ser futura")
        return value


class PetResponse(BaseModel):
    """Datos de una mascota registrada en la clínica."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    species: Species
    birth_date: date
    owner_id: int


class AppointmentCreate(BaseModel):
    """Datos de reserva de un turno."""

    pet_id: int
    vet_id: int
    start_at: datetime


class AppointmentResponse(BaseModel):
    """Datos de un turno del calendario de la clínica."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    pet_id: int
    vet_id: int
    start_at: datetime
    end_at: datetime
    status: AppointmentStatus
