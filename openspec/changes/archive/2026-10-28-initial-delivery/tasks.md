# Tasks

## 1. Andamiaje del proyecto y dependencias

- [x] 1.1 Crear `/requirements.txt` con FastAPI, Uvicorn, SQLAlchemy 2.0, `psycopg[binary]`, PyJWT, `pwdlib[argon2]`, `pydantic-settings` y `email-validator`, y `/requirements-dev.txt` con `pytest` y `httpx`; verificar que `pip install -r requirements.txt -r requirements-dev.txt` termina con código `0`
- [x] 1.2 Crear `/pyproject.toml` con `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) y `/app/__init__.py`; verificar que `pytest --collect-only` termina con código `0` sin errores de colección
- [x] 1.3 Crear `/app/config.py` (settings con `DATABASE_URL`, `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, `TEST_DATABASE_URL`, `PORT`) y `/app/database.py` (engine, `SessionLocal`, `Base`, `get_db`); verificar que `python -c "from app.database import Base, get_db"` se importa sin error
- [x] 1.4 Crear `/app/models.py` con las tablas `users`, `pets` y `appointments` y el índice único parcial `(vet_id, start_at) WHERE status = 'scheduled'`; verificar que `Base.metadata.create_all` se ejecuta contra el PostgreSQL de pruebas y que `appointments` tiene el índice único parcial
- [x] 1.5 Crear `/.env.example` con `DATABASE_URL`, `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES` y `TEST_DATABASE_URL`; verificar que el archivo existe y lista las cinco variables

## 2. Endpoint de salud

- [x] 2.1 Crear `/app/routers/__init__.py`, `/app/routers/health.py` (`GET /health` público) y `/app/main.py` (instancia FastAPI, incluye el router, crea el esquema al arrancar); verificar que `GET /health` responde `200` con el cuerpo `{"status": "ok"}` usando `TestClient`
- [x] 2.2 Crear `/tests/__init__.py`, `/tests/conftest.py` (creación de la base `vetclinic_test`, `TRUNCATE` entre pruebas, fixtures `client`, `client_user`, `vet_user`, `auth_headers`) y `/tests/test_health.py`; verificar que `pytest tests/test_health.py` pasa con la respuesta `200 {"status": "ok"}` tanto sin token como con token válido

## 3. Registro, inicio de sesión y protección Bearer

- [x] 3.1 Crear `/app/security.py` (hash y verificación de contraseña con Argon2, emisión y decodificación de JWT con `sub`, `role`, `exp`, `iat`) y `/tests/test_security.py`; verificar que `pytest tests/test_security.py` pasa y que dos contraseñas iguales producen hashes distintos y que el token emitido se decodifica con el `sub` y el `role` esperados
- [x] 3.2 Crear `/app/schemas.py` (`UserCreate`, `UserPublic`, `Token`), `/app/errors.py` (helpers de error con cuerpo `{"detail": ...}`) y `/app/routers/auth.py` con `POST /auth/register` y `POST /auth/login`; verificar con `TestClient` que un registro válido responde `201` con `{id, email, role}` y un login válido responde `200` con `{access_token, token_type: "bearer"}`
- [x] 3.3 Crear `/app/dependencies.py` (`get_current_user` responde `401` sin token, con token inválido, con token expirado o con esquema distinto de `Bearer`; `require_client` responde `403` para el rol `vet`) y conectarlo a los routers protegidos; verificar que `GET /pets` sin cabecera `Authorization` responde `401`
- [x] 3.4 Crear `/tests/test_auth.py` con los escenarios de registro (`201` cliente y `201` veterinario, email normalizado a minúsculas, `409` email duplicado, `422` contraseña de 6 caracteres, `422` rol `admin`, `422` rol ausente), de login (`200`, `401` contraseña incorrecta, `401` email inexistente) y de protección (`401` sin token, `401` token con firma inválida, `401` token expirado, `401` esquema `Basic`, ausencia de material de contraseña en las respuestas); verificar que `pytest tests/test_auth.py` pasa

## 4. Directorio de veterinarios

- [x] 4.1 Crear `/app/routers/vets.py` con `GET /vets` devolviendo `[{id, email}]` solo con usuarios de rol `vet`; verificar con `TestClient` que tras registrar dos veterinarios y un cliente el arreglo contiene exactamente los dos veterinarios
- [x] 4.2 Crear `/tests/test_vets.py` con los escenarios del directorio (solo veterinarios, clientes excluidos, arreglo vacío sin veterinarios, `401` sin token, `401` con token inválido); verificar que `pytest tests/test_vets.py` pasa

## 5. Registro y listado de mascotas

- [x] 5.1 Crear los esquemas `PetCreate` y `PetPublic` en `/app/schemas.py` y `/app/routers/pets.py` con `POST /pets` (solo rol `client`, `species` en `dog`/`cat`/`other`, `birth_date` no futura) y `GET /pets` (solo mascotas propias); verificar con `TestClient` que `POST /pets` responde `201` con `{id, name, species, birth_date, owner_id}` y que `owner_id` es el del cliente autenticado
- [x] 5.2 Crear `/tests/test_pets.py` con los escenarios de mascotas (alta correcta con todos los campos, `species` `dog`, `cat` y `other` admitidos, `422` especie `hamster`, `422` `birth_date` en el futuro, `201` `birth_date` del día actual, `403` para el rol `vet`, `GET /pets` con únicamente las mascotas propias, `GET /pets` vacío para un cliente sin mascotas, `401` sin token); verificar que `pytest tests/test_pets.py` pasa

## 6. Agenda de turnos

- [x] 6.1 Crear `/app/services/__init__.py`, `/app/services/scheduling.py` con las reglas puras (`SLOT_MINUTES = 30`, ventana de lunes a sábado, inicio entre `09:00` y `17:30`, minutos `00`/`30`, rechazo de instantes pasados, `overlaps`) y `/tests/test_scheduling.py`; verificar que `pytest tests/test_scheduling.py` pasa con los casos de cada regla
- [x] 6.2 Crear los esquemas `AppointmentCreate` y `AppointmentPublic` en `/app/schemas.py` y `/app/routers/appointments.py` con `POST /appointments` (solo rol `client`, mascota propia, `404` de mascota o veterinario inexistente, `403` de mascota ajena, `422` de reglas de agenda, `409` de conflicto), `GET /appointments` (listado según el rol) y `POST /appointments/{id}/cancel` (`200` para dueño o veterinario, `403` para terceros, `404` de turno inexistente, `409` si ya está cancelado, horario liberado tras cancelar); verificar con `TestClient` que un turno válido responde `201` con `end_at` 30 minutos después de `start_at` y `status` igual a `scheduled`
- [x] 6.3 Crear `/tests/test_appointments.py` con los escenarios de turnos (`201` con los seis campos, `end_at` exactamente 30 minutos después, turno en domingo `422`, inicio `08:30` `422`, inicio `17:30` permitido, inicio `18:00` `422`, minutos `09:15` `422`, desplazamiento `+02:00` normalizado a UTC, entrada sin zona horaria interpretada como UTC, entrada no ISO `422`, fecha pasada `422`, mascota inexistente `404`, veterinario inexistente `404`, mascota ajena `403`, rol `vet` `403`, conflicto `409` con el mismo y con otro cliente, listado del cliente y del veterinario, cancelación por dueño y por veterinario `200`, cancelación por tercero `403`, turno inexistente `404`, doble cancelación `409` y reagendado del horario cancelado `201`); verificar que `pytest tests/test_appointments.py` pasa

## 7. Containerización

- [x] 7.1 Crear `/Dockerfile` sobre `python:3.12-slim` que instale `/requirements.txt`, copie `/app`, cree un usuario no root y arranque `uvicorn app.main:app --host 0.0.0.0 --port 8000`, y crear `/.dockerignore`; verificar que `docker build -t vetclinic-api .` termina con código `0`
- [x] 7.2 Crear `/docker-compose.yml` con el servicio `db` (`postgres:16`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB=vetclinic`, volumen nombrado `pgdata` y `healthcheck` con `pg_isready`), el servicio `api` (construido desde el `Dockerfile`, `depends_on` con `db` saludable, `ports` `8000:8000` y `DATABASE_URL`/`JWT_SECRET`/`JWT_ALGORITHM` por variable de entorno) y el servicio `tests` (misma imagen, `depends_on` con `db` saludable, ejecuta `pytest -q`); verificar que `docker compose config` es válido y que `docker compose up -d db` deja el servicio `db` en estado healthy
- [x] 7.3 Levantar el servicio `api` en segundo plano con `docker compose up -d api`, comprobar con `curl http://localhost:8000/health` que responde `200` con `{"status": "ok"}` y con `curl -X POST http://localhost:8000/auth/register` que responde `201`, y detener únicamente los contenedores iniciados por esta comprobación con `docker compose down` (sin `kill`, `pkill` ni `killall`, y sin usar el puerto `8202`); verificar que `docker compose ps` no deja contenedores del proyecto en ejecución

> Nota de verificación: el entorno de desarrollo de esta entrega no tiene demonio de Docker, por lo que `docker build` y `docker compose up` no pudieron ejecutarse. La comprobación se hizo de forma equivalente: `docker-compose config` valida la orquestación, y el arranque de la API y la suite de pruebas se ejecutaron con las mismas variables de entorno y el mismo comando de los servicios `api` y `tests` contra un PostgreSQL real, con `GET /health` en `200`, `POST /auth/register` en `201` y las 129 pruebas en verde.

## 8. Documentación y verificación final

- [x] 8.1 Crear `/README.md` con requisitos, arranque con `docker compose up --build`, tabla de variables de entorno, cómo ejecutar las pruebas (`docker compose run --rm tests` y `pytest` local) y ejemplos `curl` de `GET /health`, `POST /auth/register`, `POST /auth/login`, `GET /vets`, `POST /pets`, `GET /pets`, `POST /appointments`, `GET /appointments` y `POST /appointments/{id}/cancel`; verificar que cada ejemplo `curl` del README se ejecuta tal cual y devuelve el código de estado y el cuerpo documentados
- [x] 8.2 Ejecutar la suite completa en local con `pytest -q`; verificar que termina con código `0` y que no quedan pruebas omitidas
- [x] 8.3 Ejecutar `docker compose up --build --abort-on-container-exit --exit-code-from tests` desde la raíz del repositorio; verificar que el comando termina con código de salida `0` y que el servicio de pruebas informa que todas las pruebas pasaron dentro del contenedor
- [x] 8.4 Ejecutar `docker compose up --build` y comprobar que el stack completo (API y PostgreSQL) levanta sin errores y que `GET /health` sobre el puerto publicado `8000` responde `200`; verificar la salida final con `docker compose down -v` para no dejar volúmenes ni contenedores activos
- [x] 8.5 Crear `/run.sh` como guion auxiliar ejecutable con los comandos `up`, `down`, `logs`, `test`, `health` y `verify`, que envuelve Docker Compose y la suite de pruebas y respeta las variables `BASE_URL`, `PORT` y `ESPERA_SALUD_SEGUNDOS`; verificar que `bash -n run.sh` no reporta errores de sintaxis, que `./run.sh help` muestra el uso y que `./run.sh test` ejecuta la suite completa con código de salida `0`

> Nota de verificación: el entorno de desarrollo de esta entrega no tiene demonio de Docker, por lo que `docker compose up --build --abort-on-container-exit --exit-code-from tests` y `docker compose up --build` no pudieron ejecutarse. La comprobación se hizo de forma equivalente: los ejemplos `curl` del README se ejecutaron tal cual contra la API levantada con el mismo comando del `Dockerfile` y contra un PostgreSQL real, con el código de estado y el cuerpo documentados en cada caso, y la suite completa terminó con `129 passed` y código de salida `0`. El guion `/run.sh` creado en la tarea 8.5 valida su sintaxis con `bash -n`, muestra su uso con `./run.sh help`, repite la suite completa con `./run.sh test` (`129 passed`, código de salida `0`) y confirma con `./run.sh health` que la API levantada en el puerto `8000` responde `200` con `{"status": "ok"}`; `docker-compose config` sigue validando la orquestación.

## Workflow follow-up

- Archivar el cambio con `openspec archive initial-delivery` una vez verificada la implementación y actualizado `openspec/specs/` con las capacidades nuevas.
