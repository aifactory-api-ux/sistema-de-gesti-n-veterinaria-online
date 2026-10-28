"""Reglas puras de la agenda de turnos.

Este módulo no accede a la base de datos: concentra las reglas de la agenda en
funciones que se pueden verificar de forma aislada.

Reglas que aplica:

- cada turno dura `SLOT_MINUTES` minutos;
- la agenda atiende de lunes a sábado;
- el inicio admisible va de las `09:00` a las `17:30` (UTC), de modo que el
  turno termina siempre antes de las `18:00`;
- los minutos de inicio son `00` o `30`;
- no se admiten instantes pasados;
- `overlaps` detecta el solapamiento de dos intervalos `[inicio, fin)`.
"""

from datetime import datetime, timedelta, timezone

# Duración de cada turno, en minutos.
SLOT_MINUTES = 30

# Hora de apertura de la agenda: 09:00 UTC.
OPEN_HOUR = 9
OPEN_MINUTE = OPEN_HOUR * 60

# Último inicio admitido: 17:30 UTC (el turno termina a las 18:00).
LAST_START_MINUTE = 17 * 60 + 30

# Días con agenda: de lunes (0) a sábado (5).
DIAS_DE_AGENDA = (0, 1, 2, 3, 4, 5)

# Mensajes de rechazo de la agenda.
ERROR_DIA_FUERA_DE_AGENDA = "La clínica atiende de lunes a sábado."
ERROR_FUERA_DE_HORARIO = "El turno debe empezar entre las 09:00 y las 17:30 (UTC)."
ERROR_MINUTOS_NO_ADMITIDOS = "El turno debe empezar en punto o en y media."
ERROR_INSTANTE_PASADO = "El turno no puede estar en el pasado."


def normalizar_utc(momento: datetime) -> datetime:
    """Devuelve el instante en UTC.

    Los instantes sin zona horaria se interpretan como UTC, tal y como fija el
    contrato de la API, y los que la llevan se convierten a UTC.
    """
    if momento.tzinfo is None:
        return momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(timezone.utc)


def slot_end(start_at: datetime) -> datetime:
    """Devuelve el instante de fin de un turno que empieza en `start_at`."""
    return normalizar_utc(start_at) + timedelta(minutes=SLOT_MINUTES)


def validate_slot(start_at: datetime, now: datetime) -> str | None:
    """Comprueba un inicio de turno y devuelve el primer error encontrado.

    Devuelve `None` cuando el inicio cumple todas las reglas de la agenda y el
    mensaje del primer incumplimiento en caso contrario. Todas las
    comparaciones se hacen en UTC.
    """
    inicio = normalizar_utc(start_at)
    referencia = normalizar_utc(now)

    if inicio.weekday() not in DIAS_DE_AGENDA:
        return ERROR_DIA_FUERA_DE_AGENDA

    minuto_del_dia = inicio.hour * 60 + inicio.minute
    if minuto_del_dia < OPEN_MINUTE or minuto_del_dia > LAST_START_MINUTE:
        return ERROR_FUERA_DE_HORARIO

    if inicio.minute not in (0, 30):
        return ERROR_MINUTOS_NO_ADMITIDOS

    if inicio <= referencia:
        return ERROR_INSTANTE_PASADO

    return None


def overlaps(
    a_start: datetime,
    a_end: datetime,
    b_start: datetime,
    b_end: datetime,
) -> bool:
    """Indica si los intervalos `[a_start, a_end)` y `[b_start, b_end)` se solapan.

    Los extremos no se consideran solapamiento: un turno que termina a las
    09:30 no choca con otro que empieza a las 09:30.
    """
    inicio_a, fin_a = normalizar_utc(a_start), normalizar_utc(a_end)
    inicio_b, fin_b = normalizar_utc(b_start), normalizar_utc(b_end)
    return inicio_a < fin_b and inicio_b < fin_a
