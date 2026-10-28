"""Calendario de turnos de la clínica veterinaria."""

from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_client
from app.models import Appointment, Pet, User
from app.schemas import AppointmentCreate, AppointmentResponse

router = APIRouter(prefix="/appointments", tags=["appointments"])

# El código 422 se escribe literal para no depender del alias de Starlette,
# que fue renombrado en versiones recientes.
HTTP_422 = 422

SLOT_DURATION = timedelta(minutes=30)
FIRST_START = time(9, 0)
LAST_START = time(17, 30)
GRID_MINUTES = (0, 30)
WORKING_WEEKDAYS = (0, 1, 2, 3, 4, 5)  # lunes a sábado

INVALID_GRID = "El inicio debe caer en punto o y media, sin segundos"
INVALID_WEEKDAY = "La clínica atiende de lunes a sábado"
INVALID_HOUR = "El inicio debe estar entre las 09:00 y las 17:30"
PAST_START = "La hora de inicio no puede estar en el pasado"
UNKNOWN_PET = "La mascota no existe"
UNKNOWN_VET = "El veterinario no existe"
UNKNOWN_APPOINTMENT = "El turno no existe"
PET_NOT_OWNED = "La mascota pertenece a otro cliente"
SLOT_TAKEN = "El veterinario ya tiene un turno en ese horario"
ALREADY_CANCELLED = "El turno ya estaba cancelado"
NOT_ALLOWED_TO_CANCEL = (
    "Solo el cliente dueño de la mascota o el veterinario del turno pueden cancelarlo"
)


def _as_utc(value: datetime) -> datetime:
    """Lee un instante sin zona horaria como UTC y ajusta el que sí la trae."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _calendar_violation(start_at: datetime) -> str | None:
    """Devuelve el motivo por el que un inicio no cumple el calendario, si ocurre."""
    if start_at.minute not in GRID_MINUTES or start_at.second or start_at.microsecond:
        return INVALID_GRID
    if start_at.weekday() not in WORKING_WEEKDAYS:
        return INVALID_WEEKDAY
    if not FIRST_START <= start_at.time() <= LAST_START:
        return INVALID_HOUR
    return None


def _validate_start(start_at: datetime) -> datetime:
    """Normaliza el inicio a UTC y aplica las reglas de calendario de la clínica."""
    normalized = _as_utc(start_at)
    violation = _calendar_violation(normalized)
    if violation is not None:
        raise HTTPException(status_code=HTTP_422, detail=violation)
    return normalized


@router.post(
    "", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED
)
def create_appointment(
    payload: AppointmentCreate,
    owner: User = Depends(require_client),
    db: Session = Depends(get_db),
) -> Appointment:
    """Reserva un turno de 30 minutos para una mascota del cliente autenticado."""
    start_at = _validate_start(payload.start_at)

    pet = db.get(Pet, payload.pet_id)
    if pet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=UNKNOWN_PET)
    if pet.owner_id != owner.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=PET_NOT_OWNED)

    vet = db.get(User, payload.vet_id)
    if vet is None or vet.role != "vet":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=UNKNOWN_VET)

    if start_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=HTTP_422, detail=PAST_START)

    taken = db.scalar(
        select(Appointment).where(
            Appointment.vet_id == vet.id,
            Appointment.start_at == start_at,
            Appointment.status != "cancelled",
        )
    )
    if taken is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=SLOT_TAKEN)

    appointment = Appointment(
        pet_id=pet.id,
        vet_id=vet.id,
        start_at=start_at,
        end_at=start_at + SLOT_DURATION,
        status="scheduled",
    )
    db.add(appointment)
    try:
        db.commit()
    except IntegrityError as error:
        # Un índice único futuro sobre (vet_id, start_at) convertiría la carrera
        # en un conflicto de horario en lugar de un error interno.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=SLOT_TAKEN
        ) from error
    db.refresh(appointment)
    return appointment


@router.get("", response_model=list[AppointmentResponse])
def list_appointments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Appointment]:
    """Devuelve los turnos del cliente o del veterinario autenticado."""
    if current_user.role == "vet":
        statement = select(Appointment).where(Appointment.vet_id == current_user.id)
    else:
        statement = (
            select(Appointment)
            .join(Pet, Appointment.pet_id == Pet.id)
            .where(Pet.owner_id == current_user.id)
        )
    return list(
        db.scalars(statement.order_by(Appointment.start_at, Appointment.id))
    )


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
def cancel_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Appointment:
    """Cancela un turno, sea el cliente dueño de la mascota o su veterinario."""
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=UNKNOWN_APPOINTMENT
        )

    pet = db.get(Pet, appointment.pet_id)
    is_owner = pet is not None and pet.owner_id == current_user.id
    is_vet = appointment.vet_id == current_user.id
    if not (is_owner or is_vet):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=NOT_ALLOWED_TO_CANCEL
        )

    if appointment.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=ALREADY_CANCELLED
        )

    appointment.status = "cancelled"
    db.commit()
    db.refresh(appointment)
    return appointment
