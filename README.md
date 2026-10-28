# API de la clínica veterinaria

API REST para registrar clientes y veterinarios, gestionar las mascotas de cada
cliente y agendar turnos de 30 minutos. Está construida con FastAPI y
PostgreSQL, se entrega containerizada y la suite de pruebas se ejecuta contra
un PostgreSQL real.

## Requisitos

- Docker 24 o superior con Docker Compose v2 (recomendado).
- Alternativa local: Python 3.11 o superior y un PostgreSQL 14 o superior
  accesible.

## Arranque con Docker

```bash
docker compose up --build
```

El comando levanta tres servicios:

| Servicio | Función | Puerto publicado |
| --- | --- | --- |
| `db` | PostgreSQL 16 con la base `vetclinic` y el volumen `pgdata`. | No publicado. |
| `api` | La API REST. | `PORT` (por defecto `8000`). |
| `tests` | La suite de pruebas. | No se publica. |

La API queda disponible en `http://localhost:8000` y su documentación
interactiva en `http://localhost:8000/docs`. El esquema de la base de datos se
crea en el arranque de la API, de forma idempotente: el proyecto no incluye
migraciones.

El `Dockerfile` tiene tres etapas: `builder` instala las dependencias de
ejecución, `test` suma las dependencias de desarrollo y la suite, y `runtime`
es la imagen final de la API. La etapa `runtime` es la última del archivo, de
modo que `docker build .` produce la imagen de la API con únicamente el código
de la aplicación y sus dependencias de ejecución: ni la suite de pruebas ni
`pytest` llegan a ella. El servicio `tests` construye la etapa `test`, que sí
incluye el entorno de desarrollo.

El contenedor toma toda su configuración del entorno: cadena de conexión,
secreto de firma y puerto de escucha. La orquestación los proporciona al
servicio `api` desde el entorno del shell o desde el archivo `.env` de la raíz,
y publica el puerto de escucha en el mismo puerto del host. El repositorio no
contiene secretos de producción.

Para detener la orquestación y descartar el volumen de PostgreSQL:

```bash
docker compose down -v
```

## Arranque local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

La aplicación lee su configuración de las variables de entorno o de un archivo
`.env` en la raíz del repositorio. Copia `.env.example` a `.env` y ajusta los
valores antes de arrancar:

```bash
cp .env.example .env
```

## Guion auxiliar `run.sh`

`run.sh` envuelve los comandos de Docker Compose y de la suite de pruebas para
no repetir flags ni rutas de los servicios. No requiere argumentos:

```bash
./run.sh help
```

En el primer arranque el guion crea el archivo `.env` a partir de
`.env.example`, de modo que la configuración local queda disponible sin pasos
manuales.

| Comando | Qué hace |
| --- | --- |
| `./run.sh up` | Construye la imagen y levanta `db` y `api` en segundo plano, y espera a que `/health` responda. |
| `./run.sh down` | Detiene el stack y descarta los volúmenes de PostgreSQL. |
| `./run.sh logs [servicio]` | Muestra los logs del stack o de un servicio concreto. |
| `./run.sh test` | Ejecuta la suite en el servicio `tests` de Compose; si no hay demonio de Docker disponible, la ejecuta en local con `pytest`. |
| `./run.sh health` | Consulta `GET /health` en la API publicada. |
| `./run.sh verify` | Ejecuta la verificación completa: suite de pruebas, stack levantado y comprobación de salud, dejando el entorno limpio al terminar. |

El guion respeta estas variables opcionales: `BASE_URL` (por defecto
`http://localhost:8000`), `PORT` (por defecto `8000`) y
`ESPERA_SALUD_SEGUNDOS` (por defecto `60`).

## Variables de entorno

| Variable | Obligatoria | Valor por defecto | Descripción |
| --- | --- | --- | --- |
| `DATABASE_URL` | No | `postgresql+psycopg://vetclinic:vetclinic@localhost:5432/vetclinic` | Cadena de conexión a PostgreSQL. |
| `JWT_SECRET` | En producción | Aleatorio en cada arranque | Secreto de firma de los tokens JWT. |
| `JWT_ALGORITHM` | No | `HS256` | Algoritmo de firma de los tokens. |
| `JWT_EXPIRE_MINUTES` | No | `60` | Vigencia de los tokens en minutos. |
| `TEST_DATABASE_URL` | No | `postgresql+psycopg://vetclinic:vetclinic@localhost:5432/vetclinic_test` | Base aislada que usa la suite de pruebas. |
| `PORT` | No | `8000` | Puerto de escucha de la aplicación; el contenedor lo toma del entorno y Compose lo publica en el host. |
| `POSTGRES_USER` | No | `vetclinic` | Usuario del servicio PostgreSQL de la orquestación. |
| `POSTGRES_PASSWORD` | No | `vetclinic` | Contraseña del servicio PostgreSQL de la orquestación. |
| `POSTGRES_DB` | No | `vetclinic` | Nombre de la base de datos de la orquestación. |

El valor por defecto de `JWT_SECRET` es aleatorio y efímero: sirve para
desarrollo local, pero en producción es obligatorio fijar uno propio. Docker
Compose usa un valor de desarrollo local que también debe cambiarse antes de
desplegar.

Todas estas variables están declaradas en `.env.example`, que es la plantilla
que usa `run.sh` para crear el `.env` local. Docker Compose resuelve la
orquestación con el `.env` de la raíz o con el entorno del shell; la API recibe
la configuración ya resuelta por variables de entorno.

## Pruebas

La suite usa PostgreSQL real: `tests/conftest.py` crea la base
`vetclinic_test`, aplica el esquema y, entre pruebas, vacía las tablas y
reinicia las secuencias de identificadores.

```bash
docker compose run --rm tests
```

El servicio `tests` construye la etapa `test` del `Dockerfile`, que suma las
dependencias de desarrollo (`requirements-dev.txt`) a las de ejecución: la
suite se ejecuta dentro del contenedor, contra el PostgreSQL de la
orquestación.

En local, con una base de pruebas accesible:

```bash
pytest -q
```

El guion auxiliar cubre ambos casos:

```bash
./run.sh test
```

## Catálogo de endpoints

| Método | Ruta | Acceso | Respuesta |
| --- | --- | --- | --- |
| `GET` | `/health` | Público | `200` `{"status": "ok"}` |
| `POST` | `/auth/register` | Público | `201` `{"id", "email", "role"}` |
| `POST` | `/auth/login` | Público | `200` `{"access_token", "token_type"}` |
| `GET` | `/vets` | Autenticado | `200` `[{"id", "email"}]` |
| `POST` | `/pets` | Autenticado, rol `client` | `201` `{"id", "name", "species", "birth_date", "owner_id"}` |
| `GET` | `/pets` | Autenticado | `200` `[{"id", "name", "species", "birth_date", "owner_id"}]` |
| `POST` | `/appointments` | Autenticado, rol `client` | `201` `{"id", "pet_id", "vet_id", "start_at", "end_at", "status"}` |
| `GET` | `/appointments` | Autenticado | `200` lista de turnos según el rol |
| `POST` | `/appointments/{id}/cancel` | Autenticado, dueño o veterinario del turno | `200` turno con `status` `cancelled` |

Todas las rutas protegidas exigen la cabecera `Authorization: Bearer <token>`.
Sin cabecera, con un token inválido o con un token caducado la respuesta es
`401`.

`GET /pets` exige autenticación pero no un rol concreto: devuelve las mascotas
propias del portador del token, de modo que un cliente ve las suyas y un
veterinario recibe una lista vacía (`200` con `[]`) en lugar de un `403`.

Errores habituales:

| Situación | Respuesta |
| --- | --- |
| Email ya registrado | `409` |
| Contraseña de menos de 8 caracteres, rol o cuerpo inválido | `422` |
| Credenciales incorrectas | `401` |
| Rol sin permiso para la operación | `403` |
| Mascota, veterinario o turno inexistente | `404` |
| Veterinario con un turno activo en ese horario | `409` |
| Inicio de turno fuera de las reglas de agenda | `422` |

## Ejemplos con curl

Los ejemplos siguientes se ejecutan tal cual contra la API levantada en
`http://localhost:8000`.

### Estado del servicio

```bash
curl -s http://localhost:8000/health
```

```json
{"status":"ok"}
```

### Registro de un cliente

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "ana@example.com", "password": "secreto123", "role": "client"}'
```

```json
{"id":1,"email":"ana@example.com","role":"client"}
```

### Registro de un veterinario

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "dra.luz@example.com", "password": "secreto123", "role": "vet"}'
```

```json
{"id":2,"email":"dra.luz@example.com","role":"vet"}
```

### Inicio de sesión

```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "ana@example.com", "password": "secreto123"}'
```

```json
{"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...","token_type":"bearer"}
```

Para los ejemplos siguientes se guardan los tokens en variables de entorno:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "ana@example.com", "password": "secreto123"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

TOKEN_VET=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "dra.luz@example.com", "password": "secreto123"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
```

### Directorio de veterinarios

```bash
curl -s http://localhost:8000/vets \
  -H "Authorization: Bearer $TOKEN"
```

```json
[{"id":2,"email":"dra.luz@example.com"}]
```

### Alta de una mascota

```bash
curl -s -X POST http://localhost:8000/pets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Firulais", "species": "dog", "birth_date": "2020-05-04"}'
```

```json
{"id":1,"name":"Firulais","species":"dog","birth_date":"2020-05-04","owner_id":1}
```

### Listado de las mascotas propias

```bash
curl -s http://localhost:8000/pets \
  -H "Authorization: Bearer $TOKEN"
```

```json
[{"id":1,"name":"Firulais","species":"dog","birth_date":"2020-05-04","owner_id":1}]
```

### Agendar un turno

El inicio del turno debe caer en punto o en y media, entre las `09:00` y las
`17:30` (UTC), de lunes a sábado, y no puede estar en el pasado. El siguiente
bloque calcula el próximo inicio válido:

```bash
INICIO=$(python - <<'PY'
from datetime import datetime, timedelta, timezone
dia = datetime.now(timezone.utc) + timedelta(days=1)
while dia.weekday() == 6:
    dia += timedelta(days=1)
print(dia.replace(hour=9, minute=0, second=0, microsecond=0).isoformat())
PY
)
```

```bash
curl -s -X POST http://localhost:8000/appointments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"pet_id\": 1, \"vet_id\": 2, \"start_at\": \"$INICIO\"}"
```

```json
{"id":1,"pet_id":1,"vet_id":2,"start_at":"2027-03-01T09:00:00+00:00","end_at":"2027-03-01T09:30:00+00:00","status":"scheduled"}
```

La fecha del ejemplo es ilustrativa: la respuesta real lleva el inicio que
calcula el bloque anterior, con el mismo formato ISO 8601 en UTC.

### Listado de turnos

El cliente ve los turnos de sus mascotas y el veterinario ve los suyos:

```bash
curl -s http://localhost:8000/appointments \
  -H "Authorization: Bearer $TOKEN"
```

```json
[{"id":1,"pet_id":1,"vet_id":2,"start_at":"2027-03-01T09:00:00+00:00","end_at":"2027-03-01T09:30:00+00:00","status":"scheduled"}]
```

```bash
curl -s http://localhost:8000/appointments \
  -H "Authorization: Bearer $TOKEN_VET"
```

### Cancelar un turno

Puede cancelar el dueño de la mascota o el veterinario asignado. El horario
cancelado queda libre para volver a agendarse:

```bash
curl -s -X POST http://localhost:8000/appointments/1/cancel \
  -H "Authorization: Bearer $TOKEN"
```

```json
{"id":1,"pet_id":1,"vet_id":2,"start_at":"2027-03-01T09:00:00+00:00","end_at":"2027-03-01T09:30:00+00:00","status":"cancelled"}
```

## Reglas de la agenda

- Los turnos duran 30 minutos y empiezan en punto o en y media.
- La agenda atiende de lunes a sábado, con inicios entre las `09:00` y las
  `17:30` (UTC), de modo que el último turno termina a las `18:00`.
- `start_at` se interpreta en UTC: una entrada sin zona horaria se toma como
  UTC y los desplazamientos se normalizan a UTC.
- Un inicio en el pasado se rechaza con `422`.
- Un veterinario no puede tener dos turnos activos que se solapen: el
  conflicto responde `409`.

## Estructura del proyecto

```text
app/
  config.py            Configuración leída del entorno.
  database.py          Motor, sesión y base declarativa de SQLAlchemy.
  dependencies.py      Autenticación Bearer y control de roles.
  errors.py            Helpers de error con cuerpo {"detail": ...}.
  main.py              Instancia de FastAPI y registro de routers.
  models.py            Tablas users, pets y appointments.
  schemas.py           Esquemas de entrada y salida de la API.
  security.py          Hash de contraseñas y emisión de tokens JWT.
  routers/             Routers de health, auth, vets, pets y appointments.
  services/
    scheduling.py      Reglas puras de la agenda de turnos.
tests/                 Suite de pruebas con pytest.
Dockerfile             Imagen de la API por etapas: builder, test y runtime.
docker-compose.yml     Orquestación de db, api y tests.
.env.example           Plantilla de configuración por variables de entorno.
run.sh                 Guion auxiliar con up, down, logs, test, health y verify.
```
