"""Pruebas del calendario de turnos de la clínica."""

from datetime import datetime, time, timedelta, timezone

from fastapi.testclient import TestClient

from tests.conftest import auth_header, login, register_user


def _iso(value: datetime) -> str:
    """Formatea un instante en ISO 8601 UTC con el sufijo Z."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _next_weekday(hour: int = 9, minute: int = 0) -> datetime:
    """Devuelve el próximo instante en día laborable, de lunes a sábado."""
    day = datetime.now(timezone.utc).date() + timedelta(days=1)
    while day.weekday() == 6:
        day += timedelta(days=1)
    return datetime.combine(day, time(hour, minute), tzinfo=timezone.utc)


def _next_sunday(hour: int = 9, minute: int = 0) -> datetime:
    """Devuelve el próximo domingo a la hora pedida."""
    today = datetime.now(timezone.utc).date()
    days_ahead = (6 - today.weekday()) % 7 or 7
    return datetime.combine(
        today + timedelta(days=days_ahead), time(hour, minute), tzinfo=timezone.utc
    )


def _past_weekday(hour: int = 9, minute: int = 0) -> datetime:
    """Devuelve un instante ya pasado que aún cae en día laborable."""
    day = datetime.now(timezone.utc).date() - timedelta(days=2)
    while day.weekday() == 6:
        day -= timedelta(days=1)
    return datetime.combine(day, time(hour, minute), tzinfo=timezone.utc)


def _registrar_cliente(client: TestClient, email: str) -> tuple[int, str]:
    """Registra un cliente y devuelve su identificador y su token."""
    cuenta = register_user(client, email)
    return cuenta["id"], login(client, email)


def _registrar_vet(client: TestClient, email: str) -> tuple[int, str]:
    """Registra un veterinario y devuelve su identificador y su token."""
    cuenta = register_user(client, email, role="vet")
    return cuenta["id"], login(client, email)


def _registrar_mascota(client: TestClient, token: str, name: str = "Firulais") -> int:
    """Registra una mascota a nombre del cliente y devuelve su identificador."""
    response = client.post(
        "/pets",
        json={"name": name, "species": "dog", "birth_date": "2021-03-15"},
        headers=auth_header(token),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _agendar(
    client: TestClient, token: str, pet_id: int, vet_id: int, start_at: datetime
):
    """Envía una solicitud de turno para el instante indicado."""
    return client.post(
        "/appointments",
        json={"pet_id": pet_id, "vet_id": vet_id, "start_at": _iso(start_at)},
        headers=auth_header(token),
    )


def test_cliente_agenda_un_turno_responde_201_con_30_minutos(
    client: TestClient,
) -> None:
    """El turno se crea con estado `scheduled` y dura media hora."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_cliente)
    inicio = _next_weekday(9, 0)

    response = _agendar(client, token_cliente, pet_id, vet_id, inicio)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "pet_id", "vet_id", "start_at", "end_at", "status"}
    assert isinstance(body["id"], int)
    assert body["pet_id"] == pet_id
    assert body["vet_id"] == vet_id
    assert body["status"] == "scheduled"
    assert body["start_at"] == _iso(inicio)
    assert body["end_at"] == _iso(inicio + timedelta(minutes=30))


def test_el_turno_empieza_en_hora_y_media(client: TestClient) -> None:
    """Un inicio en y media se acepta y el turno termina a la hora en punto."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_cliente)
    inicio = _next_weekday(9, 30)

    response = _agendar(client, token_cliente, pet_id, vet_id, inicio)

    assert response.status_code == 201
    assert response.json()["end_at"] == _iso(inicio + timedelta(minutes=30))


def test_el_ultimo_turno_del_dia_responde_201(client: TestClient) -> None:
    """El último inicio permitido es a las 17:30 y el turno acaba a las 18:00."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_cliente)
    inicio = _next_weekday(17, 30)

    response = _agendar(client, token_cliente, pet_id, vet_id, inicio)

    assert response.status_code == 201
    body = response.json()
    assert body["start_at"] == _iso(inicio)
    assert body["end_at"] == _iso(inicio + timedelta(minutes=30))


def test_un_sabado_dentro_del_horario_responde_201(client: TestClient) -> None:
    """La clínica atiende también los sábados."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_cliente)
    inicio = _next_weekday(9, 0)
    while inicio.weekday() != 5:
        inicio += timedelta(days=1)

    response = _agendar(client, token_cliente, pet_id, vet_id, inicio)

    assert response.status_code == 201


def test_agendar_en_un_minuto_fuera_de_la_rejilla_responde_422(
    client: TestClient,
) -> None:
    """Un inicio en un minuto que no es 00 ni 30 se rechaza."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_cliente)

    response = _agendar(client, token_cliente, pet_id, vet_id, _next_weekday(9, 15))

    assert response.status_code == 422
    assert client.get("/appointments", headers=auth_header(token_cliente)).json() == []


def test_agendar_con_segundos_sobrantes_responde_422(client: TestClient) -> None:
    """Un inicio con segundos sobrantes se rechaza."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_cliente)
    inicio = _next_weekday(9, 0)

    response = client.post(
        "/appointments",
        json={
            "pet_id": pet_id,
            "vet_id": vet_id,
            "start_at": inicio.strftime("%Y-%m-%dT%H:%M:%S") + "30Z",
        },
        headers=auth_header(token_cliente),
    )

    assert response.status_code == 422


def test_agendar_un_domingo_responde_422(client: TestClient) -> None:
    """La clínica no atiende los domingos."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_cliente)

    response = _agendar(client, token_cliente, pet_id, vet_id, _next_sunday(9, 0))

    assert response.status_code == 422


def test_agendar_antes_de_la_apertura_responde_422(client: TestClient) -> None:
    """Un inicio anterior a las 09:00 se rechaza."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_cliente)

    response = _agendar(client, token_cliente, pet_id, vet_id, _next_weekday(8, 30))

    assert response.status_code == 422


def test_agendar_despues_del_ultimo_inicio_responde_422(client: TestClient) -> None:
    """Un inicio posterior a las 17:30 se rechaza."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_cliente)

    response = _agendar(client, token_cliente, pet_id, vet_id, _next_weekday(18, 0))

    assert response.status_code == 422


def test_agendar_en_el_pasado_responde_422(client: TestClient) -> None:
    """Un inicio ya pasado no se puede reservar."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_cliente)

    response = _agendar(client, token_cliente, pet_id, vet_id, _past_weekday(9, 0))

    assert response.status_code == 422
    assert client.get("/appointments", headers=auth_header(token_cliente)).json() == []


def test_el_inicio_con_desplazamiento_se_convierte_a_utc(client: TestClient) -> None:
    """Un inicio con offset explícito se interpreta y se devuelve en UTC."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_cliente)
    inicio_utc = _next_weekday(15, 0)
    desplazado = inicio_utc.astimezone(timezone(timedelta(hours=-3)))

    response = client.post(
        "/appointments",
        json={
            "pet_id": pet_id,
            "vet_id": vet_id,
            "start_at": desplazado.isoformat(),
        },
        headers=auth_header(token_cliente),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["start_at"] == _iso(inicio_utc)
    assert body["end_at"] == _iso(inicio_utc + timedelta(minutes=30))


def test_un_veterinario_no_puede_agendar_responde_403(client: TestClient) -> None:
    """Solo los clientes reservan turnos."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_cliente)

    response = _agendar(client, token_vet, pet_id, vet_id, _next_weekday(9, 0))

    assert response.status_code == 403
    assert client.get("/appointments", headers=auth_header(token_cliente)).json() == []


def test_agendar_una_mascota_ajena_responde_403(client: TestClient) -> None:
    """Un cliente no puede agendar una mascota que no es suya."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    _otro_id, token_otro = _registrar_cliente(client, "bruno@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_otro)

    response = _agendar(client, token_cliente, pet_id, vet_id, _next_weekday(9, 0))

    assert response.status_code == 403
    assert client.get("/appointments", headers=auth_header(token_otro)).json() == []


def test_agendar_una_mascota_inexistente_responde_404(client: TestClient) -> None:
    """Una mascota que no existe no permite crear el turno."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")

    response = _agendar(client, token_cliente, 999, vet_id, _next_weekday(9, 0))

    assert response.status_code == 404


def test_agendar_un_veterinario_inexistente_responde_404(client: TestClient) -> None:
    """Un veterinario que no existe no permite crear el turno."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    pet_id = _registrar_mascota(client, token_cliente)

    response = _agendar(client, token_cliente, pet_id, 999, _next_weekday(9, 0))

    assert response.status_code == 404


def test_agendar_una_cuenta_que_no_es_veterinario_responde_404(
    client: TestClient,
) -> None:
    """El id de un cliente no identifica a un veterinario."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    otro_id, _token_otro = _registrar_cliente(client, "bruno@example.com")
    pet_id = _registrar_mascota(client, token_cliente)

    response = _agendar(client, token_cliente, pet_id, otro_id, _next_weekday(9, 0))

    assert response.status_code == 404


def test_dos_clientes_no_pueden_agendar_el_mismo_horario_responde_409(
    client: TestClient,
) -> None:
    """El veterinario conserva un solo turno activo por horario."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    _otro_id, token_otro = _registrar_cliente(client, "bruno@example.com")
    vet_id, token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_ana = _registrar_mascota(client, token_cliente, "Firulais")
    pet_bruno = _registrar_mascota(client, token_otro, "Roco")
    inicio = _next_weekday(9, 0)

    primera = _agendar(client, token_cliente, pet_ana, vet_id, inicio)
    segunda = _agendar(client, token_otro, pet_bruno, vet_id, inicio)

    assert primera.status_code == 201
    assert segunda.status_code == 409
    turnos = client.get("/appointments", headers=auth_header(token_vet)).json()
    assert len(turnos) == 1
    assert turnos[0]["start_at"] == _iso(inicio)


def test_dos_veterinarios_pueden_agendar_a_la_misma_hora(client: TestClient) -> None:
    """Cada veterinario tiene su propia agenda."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_solis, _token_solis = _registrar_vet(client, "dra.solis@example.com")
    vet_luna, _token_luna = _registrar_vet(client, "dr.luna@example.com")
    pet_id = _registrar_mascota(client, token_cliente)
    inicio = _next_weekday(9, 0)

    primera = _agendar(client, token_cliente, pet_id, vet_solis, inicio)
    segunda = _agendar(client, token_cliente, pet_id, vet_luna, inicio)

    assert primera.status_code == 201
    assert segunda.status_code == 201


def test_el_cliente_ve_solo_los_turnos_de_sus_mascotas(client: TestClient) -> None:
    """Cada cliente ve únicamente los turnos de las mascotas que registró."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    _otro_id, token_otro = _registrar_cliente(client, "bruno@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_ana = _registrar_mascota(client, token_cliente, "Firulais")
    pet_bruno = _registrar_mascota(client, token_otro, "Roco")
    _agendar(client, token_cliente, pet_ana, vet_id, _next_weekday(9, 0))
    _agendar(client, token_otro, pet_bruno, vet_id, _next_weekday(10, 0))

    respuesta = client.get("/appointments", headers=auth_header(token_cliente))

    assert respuesta.status_code == 200
    turnos = respuesta.json()
    assert len(turnos) == 1
    assert turnos[0]["pet_id"] == pet_ana
    assert set(turnos[0]) == {"id", "pet_id", "vet_id", "start_at", "end_at", "status"}


def test_el_veterinario_ve_solo_sus_turnos(client: TestClient) -> None:
    """El veterinario ve los turnos en los que es el responsable."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_solis, token_solis = _registrar_vet(client, "dra.solis@example.com")
    vet_luna, _token_luna = _registrar_vet(client, "dr.luna@example.com")
    pet_id = _registrar_mascota(client, token_cliente)
    _agendar(client, token_cliente, pet_id, vet_solis, _next_weekday(9, 0))
    _agendar(client, token_cliente, pet_id, vet_luna, _next_weekday(10, 0))

    respuesta = client.get("/appointments", headers=auth_header(token_solis))

    assert respuesta.status_code == 200
    turnos = respuesta.json()
    assert len(turnos) == 1
    assert turnos[0]["vet_id"] == vet_solis


def test_el_cliente_propietario_cancela_su_turno(client: TestClient) -> None:
    """El dueño de la mascota cancela el turno y el estado pasa a `cancelled`."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_cliente)
    inicio = _next_weekday(9, 0)
    creado = _agendar(client, token_cliente, pet_id, vet_id, inicio).json()

    respuesta = client.post(
        f"/appointments/{creado['id']}/cancel", headers=auth_header(token_cliente)
    )

    assert respuesta.status_code == 200
    body = respuesta.json()
    assert body["status"] == "cancelled"
    assert body["id"] == creado["id"]
    assert body["pet_id"] == creado["pet_id"]
    assert body["vet_id"] == creado["vet_id"]
    assert body["start_at"] == creado["start_at"]
    assert body["end_at"] == creado["end_at"]


def test_el_veterinario_del_turno_puede_cancelarlo(client: TestClient) -> None:
    """El veterinario a cargo del turno también puede cancelarlo."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_cliente)
    creado = _agendar(client, token_cliente, pet_id, vet_id, _next_weekday(9, 0)).json()

    respuesta = client.post(
        f"/appointments/{creado['id']}/cancel", headers=auth_header(token_vet)
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "cancelled"


def test_otro_usuario_no_puede_cancelar_responde_403(client: TestClient) -> None:
    """Un cliente ajeno y un veterinario sin relación no pueden cancelar el turno."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    _otro_id, token_otro = _registrar_cliente(client, "bruno@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    _otro_vet, token_otro_vet = _registrar_vet(client, "dr.luna@example.com")
    pet_id = _registrar_mascota(client, token_cliente)
    creado = _agendar(client, token_cliente, pet_id, vet_id, _next_weekday(9, 0)).json()

    por_cliente = client.post(
        f"/appointments/{creado['id']}/cancel", headers=auth_header(token_otro)
    )
    por_veterinario = client.post(
        f"/appointments/{creado['id']}/cancel", headers=auth_header(token_otro_vet)
    )

    assert por_cliente.status_code == 403
    assert por_veterinario.status_code == 403
    turnos = client.get("/appointments", headers=auth_header(token_cliente)).json()
    assert turnos[0]["status"] == "scheduled"


def test_cancelar_un_turno_ya_cancelado_responde_409(client: TestClient) -> None:
    """Un turno cancelado no se puede cancelar otra vez."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_id = _registrar_mascota(client, token_cliente)
    creado = _agendar(client, token_cliente, pet_id, vet_id, _next_weekday(9, 0)).json()

    primera = client.post(
        f"/appointments/{creado['id']}/cancel", headers=auth_header(token_cliente)
    )
    segunda = client.post(
        f"/appointments/{creado['id']}/cancel", headers=auth_header(token_cliente)
    )

    assert primera.status_code == 200
    assert segunda.status_code == 409
    turnos = client.get("/appointments", headers=auth_header(token_cliente)).json()
    assert turnos[0]["status"] == "cancelled"


def test_cancelar_un_turno_inexistente_responde_404(client: TestClient) -> None:
    """Un identificador de turno desconocido no existe."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")

    respuesta = client.post(
        "/appointments/999/cancel", headers=auth_header(token_cliente)
    )

    assert respuesta.status_code == 404


def test_el_horario_cancelado_vuelve_a_estar_disponible(client: TestClient) -> None:
    """Un turno cancelado libera el horario para volver a reservarlo."""
    _cliente_id, token_cliente = _registrar_cliente(client, "ana@example.com")
    _otro_id, token_otro = _registrar_cliente(client, "bruno@example.com")
    vet_id, _token_vet = _registrar_vet(client, "dra.solis@example.com")
    pet_ana = _registrar_mascota(client, token_cliente, "Firulais")
    pet_bruno = _registrar_mascota(client, token_otro, "Roco")
    inicio = _next_weekday(9, 0)
    creado = _agendar(client, token_cliente, pet_ana, vet_id, inicio).json()
    cancelado = client.post(
        f"/appointments/{creado['id']}/cancel", headers=auth_header(token_cliente)
    )
    assert cancelado.status_code == 200

    reservada = _agendar(client, token_otro, pet_bruno, vet_id, inicio)

    assert reservada.status_code == 201
    assert reservada.json()["status"] == "scheduled"
