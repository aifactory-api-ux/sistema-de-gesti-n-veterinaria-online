# Design

## Context

El repositorio está vacío salvo la estructura de OpenSpec (`openspec/`) y no existe código de aplicación previo. La primera entrega debe ser autocontenida: API REST con FastAPI, persistencia en PostgreSQL, autenticación JWT, suite de pruebas con `pytest` y empaquetado containerizado.

Restricciones que vienen de la solicitud original y que condicionan el diseño:

- Los códigos de estado y los cuerpos de respuesta están fijados por la solicitud (`200`, `201`, `401`, `403`, `404`, `409`, `422`).
- `start_at` es UTC ISO 8601 y la agenda funciona de lunes a sábado, de `09:00` a `18:00`, con turnos de 30 minutos que empiezan en punto o y media.
- El proyecto siempre se entrega containerizado: `Dockerfile` y `docker-compose.yml` en la raíz del repositorio.
- El equipo es solo el agente Developer (sin QA ni DevSec): las pruebas las escribe el Developer y cada grupo de tareas entrega sus propias pruebas.

Ver `proposal.md` para la motivación y `specs/` para el contrato de comportamiento.

## Goals / Non-Goals

**Goals:**

- Implementar todos los endpoints y códigos de estado definidos en las specs, sin desviaciones.
- Separar la lógica de negocio comprobable (reglas de agenda, hash de contraseñas, emisión/validación de token) del enrutamiento HTTP para que sea testeable de forma aislada.
- Que la suite de pruebas se ejecute de verdad contra PostgreSQL dentro del contenedor, de modo que la entrega se pueda verificar con `docker compose up --build`.
- Entregar el `README.md` con arranque y ejemplos `curl` de cada endpoint.

**Non-Goals:**

- Interfaz web, roles de administrador, notificaciones, pagos, multi-clínica e historial clínico: no están solicitados.
- Migraciones versionadas (Alembic): la entrega inicial crea el esquema al arrancar; se documenta como límite aceptado.
- Rate limiting, CORS, refresh tokens y revocación de tokens: fuera de la solicitud actual.

## Decisions

### 1. Estructura de archivos

Todo el código vive bajo la raíz del repositorio. Los paths exactos a crear son:

| Path | Contenido |
| --- | --- |
| `/app/__init__.py` | Paquete de la aplicación. |
| `/app/main.py` | Punto de entrada: instancia FastAPI, incluye los routers, crea el esquema en el arranque, expone `GET /health`. |
| `/app/config.py` | Settings con `pydantic-settings`: `DATABASE_URL`, `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, `TEST_DATABASE_URL`, `PORT`. |
| `/app/database.py` | Engine SQLAlchemy, `SessionLocal`, `Base`, `get_db` y creación del esquema. |
| `/app/models.py` | Modelos ORM `User`, `Pet`, `Appointment`. |
| `/app/schemas.py` | Modelos Pydantic de entrada y salida (`UserCreate`, `UserPublic`, `Token`, `PetCreate`, `PetPublic`, `VetPublic`, `AppointmentCreate`, `AppointmentPublic`). |
| `/app/security.py` | Hash y verificación de contraseñas, emisión y decodificación del JWT. |
| `/app/dependencies.py` | Dependencias FastAPI: `get_current_user` (401), `require_client` (403), `require_vet` (403). |
| `/app/services/__init__.py` | Paquete de servicios de dominio. |
| `/app/services/scheduling.py` | Reglas de agenda en funciones puras: `SLOT_MINUTES`, `OPEN_HOUR`, `LAST_START_MINUTE`, `validate_slot`, `overlaps`. |
| `/app/routers/__init__.py` | Paquete de routers. |
| `/app/routers/health.py` | `GET /health`. |
| `/app/routers/auth.py` | `POST /auth/register`, `POST /auth/login`. |
| `/app/routers/vets.py` | `GET /vets`. |
| `/app/routers/pets.py` | `POST /pets`, `GET /pets`. |
| `/app/routers/appointments.py` | `POST /appointments`, `GET /appointments`, `POST /appointments/{id}/cancel`. |
| `/app/errors.py` | Helpers de error: `conflict()`, `forbidden()`, `unauthorized()` con cuerpo `{"detail": ...}` consistente. |
| `/tests/__init__.py` | Paquete de pruebas. |
| `/tests/conftest.py` | Fixtures: base de datos de pruebas, sesión limpia, `client`, `client_user`, `vet_user`, `auth_headers`. |
| `/tests/test_health.py` | Pruebas del endpoint de salud. |
| `/tests/test_auth.py` | Pruebas de registro, login y protección Bearer. |
| `/tests/test_vets.py` | Pruebas del directorio de veterinarios. |
| `/tests/test_pets.py` | Pruebas de registro y listado de mascotas. |
| `/tests/test_appointments.py` | Pruebas de reserva, listado, conflictos y cancelación. |
| `/requirements.txt` | Dependencias de ejecución. |
| `/requirements-dev.txt` | Dependencias de desarrollo (`pytest`, `httpx`). |
| `/pyproject.toml` | Configuración de `pytest` y metadatos del proyecto. |
| `/Dockerfile` | Imagen de la API. |
| `/docker-compose.yml` | Orquestación de `db`, `api` y `tests`. |
| `/.dockerignore` | Exclusiones del contexto de build. |
| `/.env.example` | Plantilla de variables de entorno. |
| `/README.md` | Arranque local y con Docker, y ejemplos `curl`. |

### 2. Stack de aplicación

FastAPI con SQLAlchemy 2.0 en modo síncrono y driver `psycopg` (v3) para PostgreSQL.

**Por qué síncrono:** el conjunto de operaciones (alta de usuario, validación de turno, insert) son cortas y no hay I/O remoto de alta latencia; el modo síncrono evita el acoplamiento de `asyncpg`/`await` y simplifica las transacciones y las fixtures de `pytest`. Se elige sobre SQLAlchemy asíncrono + `asyncpg` porque no aporta rendimiento en esta carga y complica la gestión de sesiones en los tests. Se elige sobre SQLAlchemy síncrono + `psycopg2` porque `psycopg` v3 es el driver soportado oficialmente por PostgreSQL desde 2022.

### 3. Modelo de datos

- `users`: `id` (PK), `email` (UNIQUE, normalizado a minúsculas), `password_hash`, `role` (`client` | `vet`), `created_at`.
- `pets`: `id` (PK), `name`, `species` (`dog` | `cat` | `other`), `birth_date` (DATE), `owner_id` (FK `users.id`), `created_at`.
- `appointments`: `id` (PK), `pet_id` (FK `pets.id`), `vet_id` (FK `users.id`), `start_at` (TIMESTAMPTZ), `end_at` (TIMESTAMPTZ), `status` (`scheduled` | `cancelled`), `created_at`.

Se añade un índice único parcial `UNIQUE (vet_id, start_at) WHERE status = 'scheduled'` que impide a nivel de base de datos dos turnos activos del mismo veterinario en el mismo horario. La comprobación de solapamiento se hace en la capa de aplicación y el índice actúa como red de seguridad: ante `IntegrityError` la API responde `409`.

**Por qué índice parcial y no una columna `is_active`:** el requisito de "un horario cancelado queda libre para volver a agendarse" se traduce directamente en un índice que solo cubre filas `scheduled`, de modo que la cancelación libera el horario sin pasos extra de limpieza.

### 4. Autenticación y autorización

- Contraseñas con `pwdlib` sobre Argon2 (`argon2-cffi`), hash con sal por usuario. Se descarta `passlib` + `bcrypt` por su historial de incompatibilidades con las versiones modernas de `bcrypt`.
- JWT firmado con `HS256` usando `PyJWT`. Claims: `sub` (id de usuario), `role`, `exp`, `iat`. `token_type` de la respuesta de login es siempre `bearer`.
- Dependencia `get_current_user` construida sobre `HTTPBearer(auto_error=False)`: con `auto_error=True` FastAPI respondería `403` en vez de `401` cuando falta la cabecera, y la solicitud exige `401`. El error se emite con `HTTPException(401, headers={"WWW-Authenticate": "Bearer"})`.
- `require_client` y `require_vet` devuelven `403` cuando el rol no corresponde. Se aplica sobre `POST /pets` y `POST /appointments` (solo clientes).

**Por qué 403 y no 404 para "mascota ajena":** la especificación distingue explícitamente `403` (la mascota existe pero pertenece a otro usuario) de `404` (la mascota no existe), por lo que la comprobación de existencia se ejecuta antes que la de propiedad.

### 5. Validación de la agenda

`app/services/scheduling.py` concentra las reglas en funciones puras, sin acceso a base de datos:

- `SLOT_MINUTES = 30`, `OPEN_TIME = 09:00`, `LAST_START = 17:30` (de modo que el turno termina a más tardar a las `18:00`), días válidos de lunes (0) a sábado (5).
- `validate_slot(start_at, now)` devuelve el primer error encontrado o `None`, y evalúa **en UTC**: fuera de día (domingo) → `422`; hora de inicio anterior a `09:00` o posterior a `17:30` → `422`; minutos distintos de `00`/`30` → `422`; instante no posterior a `now` → `422`.
- `overlaps(a_start, a_end, b_start, b_end)` compara intervalos `[start, end)` para detectar choques reales y no solo coincidencias exactas de `start_at`.

La validación por parseo (ISO 8601) la hace Pydantic en el modelo de entrada y produce `422` de forma nativa antes de entrar al handler. La falta de zona horaria se interpreta como UTC y los desplazamientos se normalizan a UTC, tal y como fija la spec.

**Orden de comprobaciones en `POST /appointments`** (determinista y documentado para los tests): `401` (sin token) → `403` (rol) → `404` (mascota inexistente) → `403` (mascota ajena) → `404` (veterinario inexistente) → `422` (reglas de agenda) → `409` (conflicto de horario) → `201`.

### 6. Formato de respuestas y errores

Los cuerpos de éxito usan exactamente las claves pedidas: `{id, email, role}`, `{access_token, token_type}`, `[{id, email}]`, `{id, name, species, birth_date, owner_id}`, `{id, pet_id, vet_id, start_at, end_at, status}`.

Los errores usan `HTTPException`, por lo que el cuerpo es `{"detail": "..."}`; los errores de validación de Pydantic conservan su lista de detalle habitual con código `422`. `start_at` y `end_at` se serializan en ISO 8601 con desplazamiento UTC (`2027-03-01T09:00:00+00:00`), y `birth_date` como `YYYY-MM-DD`.

### 7. Base de datos de pruebas

`tests/conftest.py` crea la base `vetclinic_test` a partir de `TEST_DATABASE_URL` (apuntando al mismo servidor PostgreSQL que la aplicación), aplica el esquema con `Base.metadata.create_all` y, entre pruebas, hace `TRUNCATE` de `appointments`, `pets` y `users` y reinicia la secuencia de ids. Se usa PostgreSQL real (no SQLite) porque las specs mencionan índices parciales, `TIMESTAMPTZ` y `IntegrityError` por email duplicado, y SQLite no reproduce esos comportamientos.

Las pruebas usan `fastapi.testclient.TestClient`, que ejercita la aplicación completa (routing, dependencias, validaciones y base de datos) sin necesidad de levantar un servidor.

### 8. Containerización

`/Dockerfile` (stage único sobre `python:3.12-slim`): instala `requirements.txt`, copia `app/`, crea un usuario no root, y su `CMD` ejecuta `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

`/docker-compose.yml` define tres servicios:

- `db`: `postgres:16`, con `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB=vetclinic`, volumen nombrado `pgdata` y `healthcheck` con `pg_isready`.
- `api`: construye desde el `Dockerfile`, depende de `db` ya saludable, expone `8000:8000` y recibe `DATABASE_URL`, `JWT_SECRET` y `JWT_ALGORITHM` por variables de entorno.
- `tests`: construye la misma imagen, depende de `db` ya saludable, y ejecuta `pytest -q`; comparte la red con `db`.

La verificación final es `docker compose up --build --abort-on-container-exit --exit-code-from tests`, que termina con código `0` cuando la suite pasa dentro del contenedor, más una comprobación funcional de `GET /health` sobre el servicio `api` levantado.

El puerto publicado es `8000` (no se usa `8202`).

### 9. README

`/README.md` documenta: requisitos, arranque con `docker compose up --build`, variables de entorno, cómo ejecutar los tests (`docker compose run --rm tests` y `pytest` local), el catálogo de endpoints y ejemplos `curl` para cada uno: registro, login, listado de veterinarios, alta y listado de mascotas, creación, listado y cancelación de turnos.

## Risks / Trade-offs

- **La API y la base de datos comparten la imagen y la suite corre contra el servicio `db` de Compose** → si el `db` no está listo, la suite falla al conectar. Mitigación: `healthcheck` con `pg_isready` y `depends_on: condition: service_healthy`.
- **El email duplicado depende de una carrera entre el `SELECT` previo y el `INSERT`** → mitigación: índice `UNIQUE` en `users.email` y captura de `IntegrityError` que traduce a `409`.
- **No hay migraciones (Alembic)** → un cambio de esquema futuro requeriría recrear la base. Mitigación aceptada para la entrega inicial; se documenta en el README y se sugiere `create_all` idempotente en el arranque.
- **`JWT_SECRET` con valor por defecto** solo dentro de Compose → riesgo si se despliega así en producción. Mitigación: el valor por defecto es exclusivo del entorno local y el README indica generar uno propio; en producción la variable es obligatoria.
- **El índice único parcial cubre el mismo `start_at` pero no solapamientos parciales** → mitigación: la comprobación de solapamiento en `app/services/scheduling.py` se ejecuta siempre antes del `INSERT`.
- **La hora del servidor se usa para validar "no está en el pasado"** → un reloj desfasado rechazaría turnos válidos. Mitigación: se usa `datetime.now(timezone.utc)` de forma consistente en toda la API y el README documenta el requisito de NTP.
- **`JWT_EXPIRE_MINUTES` corto** → un token caduca durante una sesión de trabajo. Mitigación: valor por defecto de 60 minutos y variable configurable por entorno.

## Migration Plan

No hay migración de datos: es la primera entrega y no existe un sistema previo que migrar. El orden de despliegue es `docker compose up --build`, que crea la base vacía y el esquema en el arranque del servicio `api`. Para revertir basta con `docker compose down -v`, que descarta el volumen de PostgreSQL.

## Open Questions

Ninguna. Todas las decisiones que afectan a las specs, al enfoque y al desglose de tareas están resueltas en este documento.
