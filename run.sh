#!/usr/bin/env bash
#
# Guion auxiliar de operación de la API de la clínica veterinaria.
#
# Envuelve los comandos de Docker Compose y de la suite de pruebas para que el
# equipo pueda levantar, comprobar y detener el proyecto con una sola orden,
# sin repetir los flags largos ni las rutas de los servicios.
#
# Uso:
#   ./run.sh <comando> [argumentos]
#
# Comandos:
#   up        Construye la imagen y levanta la API y PostgreSQL en segundo plano.
#   down      Detiene el stack y elimina contenedores y volúmenes.
#   logs      Muestra los logs del stack o de un servicio concreto.
#   test      Ejecuta la suite de pruebas en el servicio `tests`.
#   health    Consulta GET /health en la API publicada.
#   verify    Ejecuta la verificación completa: pruebas, stack y comprobación de salud.
#   help      Muestra esta ayuda.
#
# Variables de entorno reconocidas:
#   BASE_URL                URL base de la API (por defecto http://localhost:8000).
#   PORT                    Puerto publicado de la API (por defecto 8000).
#   ESPERA_SALUD_SEGUNDOS   Espera máxima al comprobar la salud (por defecto 60).
#   TEST_DATABASE_URL       Base de pruebas usada por la suite en modo local.
#
# En el primer arranque se crea el archivo `.env` a partir de `.env.example`;
# a partir de ahí Compose resuelve la configuración con sus valores.

set -euo pipefail

RAIZ="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$RAIZ"

# Crea la configuración local a partir de la plantilla en el primer arranque.
if [ ! -f .env ]; then
    cp .env.example .env
    printf '✓ Archivo .env creado a partir de .env.example\n'
fi

PUERTO="${PORT:-8000}"
BASE_URL="${BASE_URL:-http://localhost:${PUERTO}}"
ESPERA_SALUD_SEGUNDOS="${ESPERA_SALUD_SEGUNDOS:-60}"

COMPOSE=""

# --- Utilidades --------------------------------------------------------------

mostrar_ayuda() {
    sed -n '3,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

registrar() {
    printf '\n==> %s\n' "$1"
}

fallar() {
    printf 'ERROR: %s\n' "$1" >&2
    exit 1
}

# Localiza el comando de Docker Compose disponible en el sistema.
detectar_compose() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE="docker compose"
        return 0
    fi
    if command -v docker-compose >/dev/null 2>&1; then
        COMPOSE="docker-compose"
        return 0
    fi
    return 1
}

# Ejecuta Docker Compose con los argumentos recibidos.
compose() {
    if [ -z "$COMPOSE" ]; then
        fallar "No se encontró Docker Compose: instálalo o usa el modo local de './run.sh test'."
    fi
    "$COMPOSE" "$@"
}

# Comprueba que el demonio de Docker responde antes de operar con el stack.
exigir_docker() {
    if ! docker info >/dev/null 2>&1; then
        fallar "El demonio de Docker no está disponible en esta máquina."
    fi
}

# Espera a que GET /health responda 200 y devuelve el cuerpo recibido.
esperar_salud() {
    local intentos=$((ESPERA_SALUD_SEGUNDOS * 2))
    local respuesta=""
    while [ "$intentos" -gt 0 ]; do
        respuesta="$(curl --silent --show-error --max-time 3 "$BASE_URL/health" 2>/dev/null || true)"
        case "$respuesta" in
            *'"status":"ok"'*)
                printf '%s' "$respuesta"
                return 0
                ;;
        esac
        sleep 0.5
        intentos=$((intentos - 1))
    done
    return 1
}

# --- Comandos ----------------------------------------------------------------

comando_up() {
    detectar_compose || fallar "No se encontró Docker Compose en el sistema."
    exigir_docker
    registrar "Construyendo la imagen y levantando el stack"
    compose up --build -d
    if ! esperar_salud >/dev/null; then
        compose ps
        compose logs --tail 50 api
        fallar "La API no respondió en $BASE_URL/health dentro de ${ESPERA_SALUD_SEGUNDOS}s."
    fi
    registrar "El stack está levantado y $BASE_URL/health responde 200"
}

comando_down() {
    detectar_compose || fallar "No se encontró Docker Compose en el sistema."
    registrar "Deteniendo el stack y eliminando volúmenes"
    compose down -v
}

comando_logs() {
    detectar_compose || fallar "No se encontró Docker Compose en el sistema."
    if [ "$#" -gt 0 ]; then
        compose logs --tail 100 --follow "$1"
    else
        compose logs --tail 100 --follow
    fi
}

comando_test() {
    if detectar_compose && docker info >/dev/null 2>&1; then
        registrar "Ejecutando la suite de pruebas en el servicio `tests`"
        compose run --rm tests
        return
    fi

    registrar "Docker no está disponible: se ejecuta la suite en local con pytest"
    local interprete=""
    local candidato
    for candidato in "./.venv/bin/python" "python3" "python" "/usr/local/bin/python3" "/usr/bin/python3"; do
        if command -v "$candidato" >/dev/null 2>&1 \
            && "$candidato" -c "import pytest, fastapi, sqlalchemy" >/dev/null 2>&1; then
            interprete="$candidato"
            break
        fi
    done
    if [ -z "$interprete" ]; then
        fallar "No se encontró un intérprete con pytest y las dependencias de la API: instala el entorno con 'python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt'."
    fi
    "$interprete" -m pytest -q
}

comando_health() {
    registrar "Consultando $BASE_URL/health"
    curl --silent --show-error --max-time 10 --write-out '\nCódigo de estado: %{http_code}\n' "$BASE_URL/health"
}

comando_verify() {
    detectar_compose || fallar "No se encontró Docker Compose en el sistema."
    exigir_docker

    limpiar() {
        compose down -v >/dev/null 2>&1 || true
    }
    trap limpiar EXIT

    registrar "1/4 Suite de pruebas dentro del contenedor"
    compose up --build --abort-on-container-exit --exit-code-from tests

    registrar "2/4 Levantando el stack completo"
    compose up --build -d

    registrar "3/4 Comprobación de salud"
    if ! esperar_salud >/dev/null; then
        compose ps
        compose logs --tail 50 api
        fallar "La API no respondió en $BASE_URL/health dentro de ${ESPERA_SALUD_SEGUNDOS}s."
    fi
    curl --silent --show-error --max-time 10 --write-out '\nCódigo de estado: %{http_code}\n' "$BASE_URL/health"

    registrar "4/4 Limpiando contenedores y volúmenes"
    trap - EXIT
    limpiar
    registrar "Verificación completada correctamente"
}

# --- Punto de entrada --------------------------------------------------------

case "${1:-help}" in
    up)
        comando_up
        ;;
    down)
        comando_down
        ;;
    logs)
        shift
        comando_logs "$@"
        ;;
    test)
        comando_test
        ;;
    health)
        comando_health
        ;;
    verify)
        comando_verify
        ;;
    help|-h|--help)
        mostrar_ayuda
        ;;
    *)
        mostrar_ayuda
        fallar "Comando desconocido: $1"
        ;;
esac
