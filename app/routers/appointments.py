"""Endpoints de la agenda de turnos.

`POST /appointments` reserva un turno de 30 minutos para una mascota propia,
`GET /appointments` lista los turnos del usuario autenticado según su rol y
`POST /appointments/{id}/cancel` cancela un turno, ya sea el dueño de la
mascota o el veterinario asignado.

Las comprobaciones siguen el orden documentado en el diseño: `401` (sin token)
→ `403` (rol) → `404` (mascota inexistente) → `403` (mascota ajena) → `404`
(veterinario inexistente) → `422` (reglas de agenda) → `409` (conflicto de
horario) → `201`.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_client
from app.errors import conflict, forbidden, not_found, unprocessable
from app.models import Appointment, Pet, User
from app.schemas import AppointmentCreate, AppointmentPublic
from app.services.scheduling import overlaps, slot_end, validate_slot

router = APIRouter(tags=["turnos"])

MENSAJE_MASCOTA_NO_ENCONTRADA = "No existe una mascota con ese identificador."
MENSAJE_VETERINARIO_NO_ENCONTRADO = "No existe un veterinario con ese identificador."
MENSAJE_MASCOTA_AJENA = "La mascota no pertenece al cliente autenticado."
MENSAJE_TURNO_EN_CONFLICTO = "El veterinario ya tiene un turno activo en ese horario."
MENSAJE_TURNO_NO_ENCONTRADO = "No existe un turno con ese identificador."
MENSAJE_TURNO_YA_CANCELADO = "El turno ya está cancelado."
MENSAJE_CANCELACION_NO_AUTORIZADA = (
    "Solo el dueño de la mascota o el veterinario del turno pueden cancelarlo."
)


@router.post(
    "/appointments",
    response_model=AppointmentPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Agenda un turno para una mascota propia",
)
def agendar_turno(
    datos: AppointmentCreate,
    db: Annotated[Session, Depends(get_db)],
    usuario: Annotated[User, Depends(require_client)],
) -> Appointment:
    """Reserva un turno y devuelve sus datos.

    Solo los clientes pueden agendar y solo con una mascota propia. Responde
    `404` si la mascota o el veterinario no existen, `403` si la mascota es
    ajena, `422` si el inicio no cumple las reglas de agenda y `409` si el
    veterinario ya tiene un turno activo que se solapa con el solicitado.
    """
    mascota = db.get(Pet, datos.pet_id)
    if mascota is None:
        raise not_found(MENSAJE_MASCOTA_NO_ENCONTRADA)
    if mascota.owner_id != usuario.id:
        raise forbidden(MENSAJE_MASCOTA_AJENA)

    veterinario = db.get(User, datos.vet_id)
    if veterinario is None or veterinario.role != "vet":
        raise not_found(MENSAJE_VETERINARIO_NO_ENCONTRADO)

    inicio = datos.start_at
    fin = slot_end(inicio)
    error = validate_slot(inicio, datetime.now(timezone.utc))
    if error is not None:
        raise unprocessable(error)

    turnos_activos = db.scalars(
        select(Appointment).where(
            Appointment.vet_id == veterinario.id,
            Appointment.status == "scheduled",
        )
    ).all()
    if any(
        overlaps(inicio, fin, turno.start_at, turno.end_at)
        for turno in turnos_activos
    ):
        raise conflict(MENSAJE_TURNO_EN_CONFLICTO)

    turno = Appointment(
        pet_id=mascota.id,
        vet_id=veterinario.id,
        start_at=inicio,
        end_at=fin,
        status="scheduled",
    )
    db.add(turno)
    try:
        db.commit()
    except IntegrityError:
        # El índice único parcial `(vet_id, start_at) WHERE status = 'scheduled'`
        # es la red de seguridad ante una carrera entre la comprobación previa y
        # la inserción.
        db.rollback()
        raise conflict(MENSAJE_TURNO_EN_CONFLICTO) from None
    db.refresh(turno)

    return turno


@router.get(
    "/appointments",
    response_model=list[AppointmentPublic],
    summary="Lista los turnos del usuario autenticado",
)
def listar_turnos(
    db: Annotated[Session, Depends(get_db)],
    usuario: Annotated[User, Depends(get_current_user)],
) -> list[Appointment]:
    """Devuelve los turnos del cliente (los de sus mascotas) o los del veterinario.

    La dependencia `get_current_user` exige un token Bearer válido, de modo que
    sin cabecera o con un token inválido la API responde `401` antes de llegar
    al manejador.
    """
    if usuario.role == "vet":
        consulta = select(Appointment).where(Appointment.vet_id == usuario.id)
    else:
        consulta = (
            select(Appointment)
            .join(Pet, Appointment.pet_id == Pet.id)
            .where(Pet.owner_id == usuario.id)
        )

    return list(db.scalars(consulta.order_by(Appointment.id)).all())


@router.post(
    "/appointments/{id}/cancel",
    response_model=AppointmentPublic,
    summary="Cancela un turno propio o asignado",
)
def cancelar_turno(
    id: int,
    db: Annotated[Session, Depends(get_db)],
    usuario: Annotated[User, Depends(get_current_user)],
) -> Appointment:
    """Cancela un turno y lo devuelve con `status` igual a `cancelled`.

    Responde `404` si el turno no existe, `403` si el usuario no es el dueño de
    la mascota ni el veterinario asignado y `409` si el turno ya estaba
    cancelado. Al cancelar, el horario queda libre para volver a agendarlo.
    """
    turno = db.get(Appointment, id)
    if turno is None:
        raise not_found(MENSAJE_TURNO_NO_ENCONTRADO)

    mascota = db.get(Pet, turno.pet_id)
    es_dueno = mascota is not None and mascota.owner_id == usuario.id
    es_veterinario = turno.vet_id == usuario.id
    if not (es_dueno or es_veterinario):
        raise forbidden(MENSAJE_CANCELACION_NO_AUTORIZADA)

    if turno.status == "cancelled":
        raise conflict(MENSAJE_TURNO_YA_CANCELADO)

    turno.status = "cancelled"
    db.commit()
    db.refresh(turno)

    return turno
