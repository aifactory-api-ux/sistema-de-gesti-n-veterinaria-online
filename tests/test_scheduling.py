"""Pruebas de las reglas puras de la agenda de turnos.

Las funciones de `app/services/scheduling.py` no acceden a la base de datos, de
modo que aquí se verifican de forma aislada, sin necesidad de la base de datos
de la suite.
"""

from datetime import datetime, timedelta, timezone

from app.services.scheduling import (
    DIAS_DE_AGENDA,
    ERROR_DIA_FUERA_DE_AGENDA,
    ERROR_FUERA_DE_HORARIO,
    ERROR_INSTANTE_PASADO,
    ERROR_MINUTOS_NO_ADMITIDOS,
    LAST_START_MINUTE,
    OPEN_HOUR,
    SLOT_MINUTES,
    normalizar_utc,
    overlaps,
    slot_end,
    validate_slot,
)

LUNES = 0
SABADO = 5
DOMINGO = 6

# Lunes 4 de enero de 2027 a las 08:00 UTC: referencia anterior a toda la
# ventana de agenda.
AHORA = datetime(2027, 1, 4, 8, 0, tzinfo=timezone.utc)


def _lunes(hora: int, minuto: int = 0) -> datetime:
    """Devuelve el lunes de referencia a la hora indicada, en UTC."""
    return datetime(2027, 1, 4, hora, minuto, tzinfo=timezone.utc)


def _con_desplazamiento(hora: int, minuto: int, horas: int) -> datetime:
    """Devuelve la hora local indicada con el desplazamiento horario dado."""
    return datetime(2027, 1, 4, hora, minuto, tzinfo=timezone(timedelta(hours=horas)))


# --- Constantes de la agenda -------------------------------------------------


def test_la_duracion_del_turno_es_de_30_minutos() -> None:
    assert SLOT_MINUTES == 30


def test_la_agenda_abre_a_las_9_y_el_ultimo_inicio_es_a_las_17_30() -> None:
    assert OPEN_HOUR == 9
    assert LAST_START_MINUTE == 17 * 60 + 30


def test_la_agenda_atiende_de_lunes_a_sabado() -> None:
    assert DIAS_DE_AGENDA == (LUNES, 1, 2, 3, 4, SABADO)
    assert DOMINGO not in DIAS_DE_AGENDA


# --- Validación del inicio ---------------------------------------------------


def test_un_inicio_valido_no_devuelve_error() -> None:
    assert validate_slot(_lunes(9, 0), AHORA) is None


def test_un_turno_en_domingo_se_rechaza() -> None:
    inicio = _lunes(9, 0) + timedelta(days=DOMINGO - LUNES)

    assert validate_slot(inicio, AHORA) == ERROR_DIA_FUERA_DE_AGENDA


def test_un_turno_en_sabado_se_admite() -> None:
    inicio = _lunes(9, 0) + timedelta(days=SABADO - LUNES)

    assert validate_slot(inicio, AHORA) is None


def test_un_inicio_antes_de_las_9_se_rechaza() -> None:
    assert validate_slot(_lunes(8, 30), AHORA) == ERROR_FUERA_DE_HORARIO


def test_un_inicio_a_las_17_30_se_admite() -> None:
    assert validate_slot(_lunes(17, 30), AHORA) is None


def test_un_inicio_a_las_18_se_rechaza() -> None:
    assert validate_slot(_lunes(18, 0), AHORA) == ERROR_FUERA_DE_HORARIO


def test_un_inicio_con_minutos_no_admitidos_se_rechaza() -> None:
    assert validate_slot(_lunes(9, 15), AHORA) == ERROR_MINUTOS_NO_ADMITIDOS


def test_un_inicio_en_y_media_se_admite() -> None:
    assert validate_slot(_lunes(9, 30), AHORA) is None


def test_un_instante_pasado_se_rechaza() -> None:
    inicio = _lunes(9, 0) - timedelta(days=7)

    assert validate_slot(inicio, AHORA) == ERROR_INSTANTE_PASADO


def test_un_instante_igual_al_actual_se_rechaza() -> None:
    referencia = _lunes(9, 0)

    assert validate_slot(referencia, referencia) == ERROR_INSTANTE_PASADO


def test_el_error_de_dia_tiene_prioridad_sobre_el_de_horario() -> None:
    inicio = _lunes(3, 0) + timedelta(days=DOMINGO - LUNES)

    assert validate_slot(inicio, AHORA) == ERROR_DIA_FUERA_DE_AGENDA


# --- Normalización a UTC -----------------------------------------------------


def test_las_reglas_se_evaluan_en_utc() -> None:
    # Las 11:00 con desplazamiento +02:00 son las 09:00 UTC: inicio admisible.
    inicio = _con_desplazamiento(11, 0, 2)

    assert inicio.utcoffset() == timedelta(hours=2)
    assert validate_slot(inicio, AHORA) is None


def test_un_instante_sin_zona_horaria_se_interpreta_como_utc() -> None:
    inicio = _lunes(9, 0).replace(tzinfo=None)

    assert validate_slot(inicio, AHORA) is None
    assert normalizar_utc(inicio) == _lunes(9, 0)


def test_normalizar_utc_convierte_un_desplazamiento_a_utc() -> None:
    inicio = _con_desplazamiento(11, 0, 2)

    assert normalizar_utc(inicio) == _lunes(9, 0)


# --- Cálculo del fin del turno ----------------------------------------------


def test_el_fin_del_turno_es_30_minutos_despues_del_inicio() -> None:
    assert slot_end(_lunes(9, 0)) == _lunes(9, 30)


def test_el_fin_del_turno_se_normaliza_a_utc() -> None:
    inicio = _con_desplazamiento(11, 0, 2)

    assert slot_end(inicio) == _lunes(9, 30)


# --- Detección de solapamientos ----------------------------------------------


def test_overlaps_detecta_intervalos_identicos() -> None:
    assert overlaps(_lunes(9, 0), _lunes(9, 30), _lunes(9, 0), _lunes(9, 30))


def test_overlaps_detecta_un_solapamiento_parcial() -> None:
    assert overlaps(_lunes(9, 0), _lunes(9, 30), _lunes(9, 15), _lunes(9, 45))


def test_overlaps_detecta_un_intervalo_contenido() -> None:
    assert overlaps(_lunes(9, 0), _lunes(10, 0), _lunes(9, 30), _lunes(9, 45))


def test_overlaps_no_detecta_intervalos_que_solo_se_tocan() -> None:
    assert not overlaps(_lunes(9, 0), _lunes(9, 30), _lunes(9, 30), _lunes(10, 0))


def test_overlaps_no_detecta_intervalos_en_dias_distintos() -> None:
    assert not overlaps(_lunes(9, 0), _lunes(9, 30), _lunes(10, 0), _lunes(10, 30))


def test_overlaps_compara_en_utc() -> None:
    inicio = _con_desplazamiento(11, 0, 2)

    assert overlaps(inicio, slot_end(inicio), _lunes(9, 0), _lunes(9, 30))
