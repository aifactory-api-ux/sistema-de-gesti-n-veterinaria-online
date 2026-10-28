"""Pruebas de la agenda de turnos.

Las pruebas usan instantes calculados a partir del momento actual para que
siempre caigan dentro de la ventana de agenda (lunes a sábado, de 09:00 a
17:30 UTC) y nunca en el pasado.
"""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Appointment
from app.services.scheduling import DIAS_DE_AGENDA

CONTRASENA = "secreto123"
EMAIL_CLIENTE = "ana@example.com"
EMAIL_OTRO_CLIENTE = "bruno@example.com"
EMAIL_VETERINARIO = "dra.luz@example.com"

DOMINGO = 6
SABADO = 5
DURACION_TURNO = timedelta(minutes=30)


# --- Utilidades --------------------------------------------------------------


def _registrar(client: TestClient, email: str, rol: str) -> dict:
    """Registra un usuario mediante la API y devuelve el cuerpo de la respuesta."""
    respuesta = client.post(
        "/auth/register",
        json={"email": email, "password": CONTRASENA, "role": rol},
    )
    assert respuesta.status_code == 201
    return respuesta.json()


def _token(client: TestClient, email: str) -> str:
    """Inicia sesión y devuelve el token de acceso del usuario indicado."""
    respuesta = client.post(
        "/auth/login", json={"email": email, "password": CONTRASENA}
    )
    assert respuesta.status_code == 200
    return respuesta.json()["access_token"]


def _usuario(client: TestClient, email: str, rol: str) -> tuple[dict, str]:
    """Registra un usuario, inicia sesión y devuelve su cuerpo y su token."""
    cuerpo = _registrar(client, email, rol)
    return cuerpo, _token(client, email)


def _cabecera(token: str) -> dict[str, str]:
    """Construye la cabecera `Authorization: Bearer` con el token indicado."""
    return {"Authorization": f"Bearer {token}"}


def _dia_de_agenda() -> date:
    """Devuelve la fecha del próximo día con agenda (de lunes a sábado)."""
    dia = datetime.now(timezone.utc).date() + timedelta(days=1)
    while dia.weekday() not in DIAS_DE_AGENDA:
        dia += timedelta(days=1)
    return dia


def _instante(dia: date, hora: int, minuto: int = 0) -> datetime:
    """Construye un instante en UTC a partir de una fecha y una hora."""
    return datetime.combine(dia, time(hour=hora, minute=minuto), tzinfo=timezone.utc)


def _inicio(hora: int, minuto: int = 0) -> str:
    """Devuelve el inicio ISO 8601 del próximo día de agenda a la hora dada."""
    return _instante(_dia_de_agenda(), hora, minuto).isoformat()


def _inicio_con_desplazamiento(horas: int) -> str:
    """Devuelve el inicio ISO 8601 del próximo día de agenda con otro desplazamiento."""
    utc = _instante(_dia_de_agenda(), 9, 0)
    return utc.astimezone(timezone(timedelta(hours=horas))).isoformat()


def _inicio_sin_zona() -> str:
    """Devuelve el inicio ISO 8601 del próximo día de agenda sin zona horaria."""
    return _instante(_dia_de_agenda(), 9, 0).replace(tzinfo=None).isoformat()


def _inicio_pasado() -> str:
    """Devuelve un inicio ISO 8601 de un día de agenda ya transcurrido."""
    dia = _dia_de_agenda() - timedelta(days=7)
    return _instante(dia, 9, 0).isoformat()


def _inicio_de_domingo() -> str:
    """Devuelve el inicio ISO 8601 del próximo domingo a las 09:00."""
    dia = datetime.now(timezone.utc).date() + timedelta(days=1)
    while dia.weekday() != DOMINGO:
        dia += timedelta(days=1)
    return _instante(dia, 9, 0).isoformat()


def _inicio_de_sabado() -> str:
    """Devuelve el inicio ISO 8601 del próximo sábado a las 10:00."""
    dia = datetime.now(timezone.utc).date() + timedelta(days=1)
    while dia.weekday() != SABADO:
        dia += timedelta(days=1)
    return _instante(dia, 10, 0).isoformat()


def _crear_mascota(client: TestClient, token: str, nombre: str = "Firulais") -> dict:
    """Crea una mascota con el cliente indicado y devuelve su cuerpo."""
    respuesta = client.post(
        "/pets",
        json={"name": nombre, "species": "dog", "birth_date": "2020-05-04"},
        headers=_cabecera(token),
    )
    assert respuesta.status_code == 201
    return respuesta.json()


def _total_de_turnos(sesion_local: sessionmaker[Session]) -> int:
    """Cuenta los turnos almacenados en la base de pruebas."""
    with sesion_local() as sesion:
        return len(list(sesion.scalars(select(Appointment)).all()))


# --- Reserva de turno --------------------------------------------------------


def test_agendar_turno_responde_201_con_todos_los_campos(
    client: TestClient,
) -> None:
    _registrar(client, EMAIL_CLIENTE, "client")
    veterinario = _registrar(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)

    respuesta = client.post(
        "/appointments",
        json={
            "pet_id": mascota["id"],
            "vet_id": veterinario["id"],
            "start_at": _inicio(9, 0),
        },
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"id", "pet_id", "vet_id", "start_at", "end_at", "status"}
    assert cuerpo["pet_id"] == mascota["id"]
    assert cuerpo["vet_id"] == veterinario["id"]
    assert cuerpo["status"] == "scheduled"
    assert isinstance(cuerpo["id"], int)


def test_el_turno_dura_exactamente_30_minutos(client: TestClient) -> None:
    _, token = _usuario(client, EMAIL_CLIENTE, "client")
    _, token_vet = _usuario(client, EMAIL_VETERINARIO, "vet")
    mascota = _crear_mascota(client, token)

    respuesta = client.post(
        "/appointments",
        json={
            "pet_id": mascota["id"],
            "vet_id": 2,
            "start_at": _inicio(9, 0),
        },
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    diferencia = datetime.fromisoformat(cuerpo["end_at"]) - datetime.fromisoformat(
        cuerpo["start_at"]
    )
    assert diferencia == DURACION_TURNO
    assert token_vet


def test_el_turno_se_persiste_con_la_mascota_y_el_veterinario(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)
    inicio = _inicio(9, 0)

    respuesta = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": inicio},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 201
    with sesion_local() as sesion:
        turno = sesion.get(Appointment, respuesta.json()["id"])
    assert turno is not None
    assert turno.pet_id == mascota["id"]
    assert turno.vet_id == 2
    assert turno.status == "scheduled"
    assert turno.start_at == datetime.fromisoformat(inicio)
    assert turno.end_at == datetime.fromisoformat(inicio) + DURACION_TURNO


def test_el_veterinario_no_puede_agendar_turnos(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _, token = _usuario(client, EMAIL_VETERINARIO, "vet")

    respuesta = client.post(
        "/appointments",
        json={"pet_id": 1, "vet_id": 1, "start_at": _inicio(9, 0)},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 403
    assert _total_de_turnos(sesion_local) == 0


def test_una_mascota_inexistente_responde_404(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)

    respuesta = client.post(
        "/appointments",
        json={"pet_id": 999999, "vet_id": 2, "start_at": _inicio(9, 0)},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 404
    assert _total_de_turnos(sesion_local) == 0


def test_un_veterinario_inexistente_responde_404(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _, token = _usuario(client, EMAIL_CLIENTE, "client")
    mascota = _crear_mascota(client, token)

    respuesta = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 999999, "start_at": _inicio(9, 0)},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 404
    assert _total_de_turnos(sesion_local) == 0


def test_un_usuario_que_no_es_veterinario_responde_404(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _, token = _usuario(client, EMAIL_CLIENTE, "client")
    mascota = _crear_mascota(client, token)
    _usuario(client, EMAIL_OTRO_CLIENTE, "client")

    respuesta = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio(9, 0)},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 404
    assert _total_de_turnos(sesion_local) == 0


def test_una_mascota_ajena_responde_403(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    _usuario(client, EMAIL_OTRO_CLIENTE, "client")
    token_ana = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token_ana)
    token_bruno = _token(client, EMAIL_OTRO_CLIENTE)

    respuesta = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio(9, 0)},
        headers=_cabecera(token_bruno),
    )

    assert respuesta.status_code == 403
    assert _total_de_turnos(sesion_local) == 0


def test_agendar_sin_token_responde_401(client: TestClient) -> None:
    respuesta = client.post(
        "/appointments",
        json={"pet_id": 1, "vet_id": 2, "start_at": _inicio(9, 0)},
    )

    assert respuesta.status_code == 401
    assert "detail" in respuesta.json()


def test_agendar_con_token_invalido_responde_401(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    respuesta = client.post(
        "/appointments",
        json={"pet_id": 1, "vet_id": 2, "start_at": _inicio(9, 0)},
        headers={"Authorization": "Bearer token.inventado.aaa"},
    )

    assert respuesta.status_code == 401
    assert _total_de_turnos(sesion_local) == 0


# --- Reglas de agenda --------------------------------------------------------


def test_un_turno_en_domingo_responde_422(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)

    respuesta = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio_de_domingo()},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 422
    assert _total_de_turnos(sesion_local) == 0


def test_un_turno_en_sabado_se_admite(client: TestClient) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)

    respuesta = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio_de_sabado()},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 201


def test_un_inicio_antes_de_las_9_responde_422(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)

    respuesta = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio(8, 30)},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 422
    assert _total_de_turnos(sesion_local) == 0


def test_un_inicio_a_las_17_30_se_admite(client: TestClient) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)

    respuesta = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio(17, 30)},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    inicio = datetime.fromisoformat(cuerpo["start_at"])
    fin = datetime.fromisoformat(cuerpo["end_at"])
    assert (inicio.hour, inicio.minute) == (17, 30)
    assert (fin.hour, fin.minute) == (18, 0)


def test_un_inicio_a_las_18_responde_422(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)

    respuesta = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio(18, 0)},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 422
    assert _total_de_turnos(sesion_local) == 0


def test_un_inicio_con_minutos_no_admitidos_responde_422(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)

    respuesta = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio(9, 15)},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 422
    assert _total_de_turnos(sesion_local) == 0


def test_un_inicio_en_y_media_se_admite(client: TestClient) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)

    respuesta = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio(9, 30)},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    inicio = datetime.fromisoformat(cuerpo["start_at"])
    fin = datetime.fromisoformat(cuerpo["end_at"])
    assert (inicio.hour, inicio.minute) == (9, 30)
    assert (fin.hour, fin.minute) == (10, 0)


def test_un_inicio_con_desplazamiento_se_normaliza_a_utc(client: TestClient) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)
    esperado = _instante(_dia_de_agenda(), 9, 0)

    respuesta = client.post(
        "/appointments",
        json={
            "pet_id": mascota["id"],
            "vet_id": 2,
            "start_at": _inicio_con_desplazamiento(2),
        },
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert datetime.fromisoformat(cuerpo["start_at"]) == esperado
    assert cuerpo["start_at"].endswith("+00:00")


def test_un_inicio_sin_zona_horaria_se_interpreta_como_utc(client: TestClient) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)
    esperado = _instante(_dia_de_agenda(), 9, 0)

    respuesta = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio_sin_zona()},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert datetime.fromisoformat(cuerpo["start_at"]) == esperado
    assert cuerpo["start_at"].endswith("+00:00")


def test_un_inicio_que_no_es_iso_8601_responde_422(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)

    respuesta = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": "mañana a las 9"},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 422
    assert _total_de_turnos(sesion_local) == 0


def test_un_inicio_en_el_pasado_responde_422(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)

    respuesta = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio_pasado()},
        headers=_cabecera(token),
    )

    assert respuesta.status_code == 422
    assert _total_de_turnos(sesion_local) == 0


# --- Conflicto de horario ----------------------------------------------------


def test_un_turno_duplicado_del_mismo_cliente_responde_409(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)
    inicio = _inicio(9, 0)

    primera = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": inicio},
        headers=_cabecera(token),
    )
    assert primera.status_code == 201

    segunda = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": inicio},
        headers=_cabecera(token),
    )

    assert segunda.status_code == 409
    assert _total_de_turnos(sesion_local) == 1


def test_un_turno_duplicado_de_otro_cliente_responde_409(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    _usuario(client, EMAIL_OTRO_CLIENTE, "client")
    token_ana = _token(client, EMAIL_CLIENTE)
    mascota_ana = _crear_mascota(client, token_ana, "Firulais")
    token_bruno = _token(client, EMAIL_OTRO_CLIENTE)
    mascota_bruno = _crear_mascota(client, token_bruno, "Rayo")
    inicio = _inicio(9, 0)

    primera = client.post(
        "/appointments",
        json={"pet_id": mascota_ana["id"], "vet_id": 2, "start_at": inicio},
        headers=_cabecera(token_ana),
    )
    assert primera.status_code == 201

    segunda = client.post(
        "/appointments",
        json={"pet_id": mascota_bruno["id"], "vet_id": 2, "start_at": inicio},
        headers=_cabecera(token_bruno),
    )

    assert segunda.status_code == 409
    assert _total_de_turnos(sesion_local) == 1


def test_otro_horario_del_mismo_veterinario_no_entra_en_conflicto(
    client: TestClient,
) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)

    primera = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio(9, 0)},
        headers=_cabecera(token),
    )
    assert primera.status_code == 201

    segunda = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio(10, 0)},
        headers=_cabecera(token),
    )

    assert segunda.status_code == 201


# --- Listado de turnos -------------------------------------------------------


def test_el_cliente_ve_solo_los_turnos_de_sus_mascotas(client: TestClient) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    _usuario(client, EMAIL_OTRO_CLIENTE, "client")
    token_ana = _token(client, EMAIL_CLIENTE)
    mascota_ana = _crear_mascota(client, token_ana, "Firulais")
    token_bruno = _token(client, EMAIL_OTRO_CLIENTE)
    mascota_bruno = _crear_mascota(client, token_bruno, "Rayo")

    turno_ana = client.post(
        "/appointments",
        json={"pet_id": mascota_ana["id"], "vet_id": 2, "start_at": _inicio(9, 0)},
        headers=_cabecera(token_ana),
    )
    assert turno_ana.status_code == 201
    turno_bruno = client.post(
        "/appointments",
        json={"pet_id": mascota_bruno["id"], "vet_id": 2, "start_at": _inicio(10, 0)},
        headers=_cabecera(token_bruno),
    )
    assert turno_bruno.status_code == 201

    respuesta = client.get("/appointments", headers=_cabecera(token_ana))

    assert respuesta.status_code == 200
    turnos = respuesta.json()
    assert [turno["id"] for turno in turnos] == [turno_ana.json()["id"]]


def test_el_veterinario_ve_solo_los_turnos_asignados(client: TestClient) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token_ana = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token_ana)
    token_vet = _token(client, EMAIL_VETERINARIO)

    primer_turno = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio(9, 0)},
        headers=_cabecera(token_ana),
    )
    assert primer_turno.status_code == 201
    segundo_turno = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio(10, 0)},
        headers=_cabecera(token_ana),
    )
    assert segundo_turno.status_code == 201

    respuesta = client.get("/appointments", headers=_cabecera(token_vet))

    assert respuesta.status_code == 200
    turnos = respuesta.json()
    assert {turno["id"] for turno in turnos} == {
        primer_turno.json()["id"],
        segundo_turno.json()["id"],
    }
    assert all(turno["vet_id"] == 2 for turno in turnos)


def test_el_listado_de_un_cliente_sin_turnos_devuelve_un_arreglo_vacio(
    client: TestClient,
) -> None:
    _, token = _usuario(client, EMAIL_CLIENTE, "client")

    respuesta = client.get("/appointments", headers=_cabecera(token))

    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_el_listado_sin_token_responde_401(client: TestClient) -> None:
    respuesta = client.get("/appointments")

    assert respuesta.status_code == 401
    assert "detail" in respuesta.json()


def test_el_listado_con_token_invalido_responde_401(client: TestClient) -> None:
    respuesta = client.get(
        "/appointments", headers={"Authorization": "Bearer token.inventado.aaa"}
    )

    assert respuesta.status_code == 401


# --- Cancelación de turnos ----------------------------------------------------


def test_el_dueno_de_la_mascota_puede_cancelar_el_turno(client: TestClient) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)
    turno = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio(9, 0)},
        headers=_cabecera(token),
    )
    assert turno.status_code == 201

    respuesta = client.post(
        f"/appointments/{turno.json()['id']}/cancel", headers=_cabecera(token)
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "cancelled"


def test_el_veterinario_asignado_puede_cancelar_el_turno(client: TestClient) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _, token_vet = _usuario(client, EMAIL_VETERINARIO, "vet")
    token_cliente = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token_cliente)
    turno = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio(9, 0)},
        headers=_cabecera(token_cliente),
    )
    assert turno.status_code == 201

    respuesta = client.post(
        f"/appointments/{turno.json()['id']}/cancel", headers=_cabecera(token_vet)
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "cancelled"


def test_un_usuario_no_relacionado_no_puede_cancelar_el_turno(
    client: TestClient, sesion_local: sessionmaker[Session]
) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    _usuario(client, EMAIL_OTRO_CLIENTE, "client")
    token_ana = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token_ana)
    turno = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio(9, 0)},
        headers=_cabecera(token_ana),
    )
    assert turno.status_code == 201

    respuesta = client.post(
        f"/appointments/{turno.json()['id']}/cancel",
        headers=_cabecera(_token(client, EMAIL_OTRO_CLIENTE)),
    )

    assert respuesta.status_code == 403
    with sesion_local() as sesion:
        guardado = sesion.get(Appointment, turno.json()["id"])
    assert guardado is not None
    assert guardado.status == "scheduled"


def test_cancelar_un_turno_inexistente_responde_404(client: TestClient) -> None:
    _, token = _usuario(client, EMAIL_CLIENTE, "client")

    respuesta = client.post("/appointments/999999/cancel", headers=_cabecera(token))

    assert respuesta.status_code == 404
    assert "detail" in respuesta.json()


def test_cancelar_un_turno_ya_cancelado_responde_409(client: TestClient) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)
    turno = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": _inicio(9, 0)},
        headers=_cabecera(token),
    )
    assert turno.status_code == 201
    primera = client.post(
        f"/appointments/{turno.json()['id']}/cancel", headers=_cabecera(token)
    )
    assert primera.status_code == 200

    segunda = client.post(
        f"/appointments/{turno.json()['id']}/cancel", headers=_cabecera(token)
    )

    assert segunda.status_code == 409
    assert "detail" in segunda.json()


def test_el_horario_cancelado_queda_libre(client: TestClient) -> None:
    _usuario(client, EMAIL_CLIENTE, "client")
    _usuario(client, EMAIL_VETERINARIO, "vet")
    token = _token(client, EMAIL_CLIENTE)
    mascota = _crear_mascota(client, token)
    inicio = _inicio(9, 0)
    turno = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": inicio},
        headers=_cabecera(token),
    )
    assert turno.status_code == 201
    cancelacion = client.post(
        f"/appointments/{turno.json()['id']}/cancel", headers=_cabecera(token)
    )
    assert cancelacion.status_code == 200

    nuevo = client.post(
        "/appointments",
        json={"pet_id": mascota["id"], "vet_id": 2, "start_at": inicio},
        headers=_cabecera(token),
    )

    assert nuevo.status_code == 201
    assert nuevo.json()["status"] == "scheduled"


def test_cancelar_sin_token_responde_401(client: TestClient) -> None:
    respuesta = client.post("/appointments/1/cancel")

    assert respuesta.status_code == 401
    assert "detail" in respuesta.json()


@pytest.mark.parametrize("metodo", ["get", "post"])
def test_los_turnos_exigen_autenticacion(client: TestClient, metodo: str) -> None:
    respuesta = getattr(client, metodo)("/appointments")

    assert respuesta.status_code == 401
