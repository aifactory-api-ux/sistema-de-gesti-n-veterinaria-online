# API de la clínica veterinaria

Backend REST del sistema de gestión de la clínica veterinaria: cuentas de clientes y
veterinarios, registro de mascotas y agenda de turnos de 30 minutos.

- **FastAPI** con **SQLAlchemy 2** (ORM síncrono) sobre **PostgreSQL**.
- Autenticación **JWT** (argon2 para las contraseñas, PyJWT para los tokens) con protección
  por rol y por propietario.
- Suite de **pytest** que se ejecuta sobre SQLite en memoria: ni Docker ni PostgreSQL.

## Requisitos

| Herramienta | Versión | Uso |
| --- | --- | --- |
| Python | 3.11 o superior | ejecución local y pruebas |
| PostgreSQL | 14 o superior | base de datos en la ejecución local |
| Docker y Compose v2 | opcional | ejecución en contenedores |

## Estructura del proyecto

```
app/
├── main.py           # aplicación FastAPI y montaje de los routers
├── config.py         # lectura de las variables de entorno
├── database.py       # motor, fábrica de sesiones y base declarativa
├── models.py         # tablas users, pets y appointments
├── schemas.py        # modelos de entrada y salida (Pydantic)
├── security.py       # hash argon2 y emisión/verificación de tokens JWT
├── dependencies.py   # get_current_user y require_client
└── routers/          # health, auth, vets, pets y appointments
tests/                # suite de pruebas con pytest
Dockerfile            # imagen de la API
docker-compose.yml    # API + PostgreSQL
.env.example          # variables de entorno de ejemplo
```

## Variables de entorno

| Variable | Obligatoria | Descripción | Valor por defecto |
| --- | --- | --- | --- |
| `DATABASE_URL` | sí | URL de conexión de SQLAlchemy, por ejemplo `postgresql+psycopg://clinic:clinic@localhost:5432/clinic` | — |
| `JWT_SECRET` | sí | clave de firma (HS256) de los tokens de acceso | — |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | vigencia del token de acceso en minutos | `60` |

La aplicación no arranca si falta `DATABASE_URL` o `JWT_SECRET`: el error de arranque
indica qué variables obligatorias están ausentes. `.env.example` es una plantilla
funcional para la ejecución local.

## Ejecución local

1. Crear el entorno virtual e instalar las dependencias:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt -r requirements-dev.txt
   ```

2. Preparar la base de datos y la configuración:

   ```bash
   createdb clinic
   cp .env.example .env
   ```

   En `.env`, `DATABASE_URL` apunta a `localhost`; ajústala si las credenciales o el
   puerto de PostgreSQL son otros.

3. Levantar la API:

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

   El esquema de las tablas se crea solo al arrancar, así que no hace falta ningún
   comando de migración.

La API queda en <http://localhost:8000>.

## Ejecución con Docker

```bash
docker compose up --build
```

El compose levanta dos servicios: `api`, que construye la imagen del `Dockerfile` de la
raíz y publica el puerto `8000`, y `db`, un PostgreSQL 16 con los datos en el volumen
`clinic-db-data`. La API queda en <http://localhost:8000> y su `DATABASE_URL` ya apunta
al servicio de base de datos.

La clave de firma tiene un valor de desarrollo en el compose; para usar la del equipo
interno hay que exportarla antes de arrancar:

```bash
JWT_SECRET="$(openssl rand -hex 32)" docker compose up --build
```

Para detener la pila: `docker compose down` (con `-v` se borra además el volumen de
datos).

## Pruebas

```bash
pytest -q
```

La suite usa una base SQLite en memoria, crea el esquema por sesión y limpia las tablas
entre pruebas: se ejecuta sin Docker y sin PostgreSQL. Las variables de entorno de
pruebas las fija `tests/conftest.py`.

## Documentación interactiva

Con la API en marcha: `/docs` (Swagger UI), `/redoc` y `/openapi.json`.

## Ejemplos con curl

Los ejemplos se ejecutan en orden y comparten las variables de entorno y los tokens.
Los identificadores de los ejemplos (`1`, `2`) corresponden a una base recién creada.

```bash
export BASE_URL=http://localhost:8000
```

### 1. Estado del servicio — `GET /health` → 200

```bash
curl -i "$BASE_URL/health"
# HTTP/1.1 200 OK
# {"status":"ok"}
```

### 2. Registro de un cliente — `POST /auth/register` → 201

```bash
curl -i -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "cliente@clinica.test", "password": "secreto123", "role": "client"}'
# HTTP/1.1 201 Created
# {"id":1,"email":"cliente@clinica.test","role":"client"}
```

### 3. Registro de un veterinario — `POST /auth/register` → 201

```bash
curl -i -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "veterinario@clinica.test", "password": "secreto123", "role": "vet"}'
# HTTP/1.1 201 Created
# {"id":2,"email":"veterinario@clinica.test","role":"vet"}
```

### 4. Inicio de sesión — `POST /auth/login` → 200

```bash
TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "cliente@clinica.test", "password": "secreto123"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
# HTTP/1.1 200 OK
# {"access_token":"<jwt>","token_type":"bearer"}

VET_TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "veterinario@clinica.test", "password": "secreto123"}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
```

### 5. Directorio de veterinarios — `GET /vets` → 200

```bash
curl -i "$BASE_URL/vets" -H "Authorization: Bearer $TOKEN"
# HTTP/1.1 200 OK
# [{"id":2,"email":"veterinario@clinica.test"}]
```

### 6. Alta de una mascota — `POST /pets` → 201

```bash
curl -i -X POST "$BASE_URL/pets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Roco", "species": "dog", "birth_date": "2020-05-14"}'
# HTTP/1.1 201 Created
# {"id":1,"name":"Roco","species":"dog","birth_date":"2020-05-14","owner_id":1}
```

### 7. Mascotas del cliente autenticado — `GET /pets` → 200

```bash
curl -i "$BASE_URL/pets" -H "Authorization: Bearer $TOKEN"
# HTTP/1.1 200 OK
# [{"id":1,"name":"Roco","species":"dog","birth_date":"2020-05-14","owner_id":1}]
```

### 8. Reserva de un turno — `POST /appointments` → 201

`start_at` es un instante UTC en ISO 8601. El ejemplo usa el siguiente lunes a las
09:00 UTC, que siempre cae dentro de la ventana de la clínica:

```bash
START_AT=$(date -u -d "monday +7 days 09:00" +%Y-%m-%dT%H:%M:%SZ)

curl -i -X POST "$BASE_URL/appointments" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"pet_id\": 1, \"vet_id\": 2, \"start_at\": \"$START_AT\"}"
# HTTP/1.1 201 Created
# {"id":1,"pet_id":1,"vet_id":2,"start_at":"<inicio>Z","end_at":"<inicio + 30 min>Z","status":"scheduled"}
```

### 9. Turnos del cliente o del veterinario — `GET /appointments` → 200

```bash
curl -i "$BASE_URL/appointments" -H "Authorization: Bearer $TOKEN"
# HTTP/1.1 200 OK
# [{"id":1,"pet_id":1,"vet_id":2,"start_at":"<inicio>Z","end_at":"<fin>Z","status":"scheduled"}]

curl -i "$BASE_URL/appointments" -H "Authorization: Bearer $VET_TOKEN"
# HTTP/1.1 200 OK
# [{"id":1,"pet_id":1,"vet_id":2,"start_at":"<inicio>Z","end_at":"<fin>Z","status":"scheduled"}]
```

### 10. Cancelación de un turno — `POST /appointments/{appointment_id}/cancel` → 200

```bash
curl -i -X POST "$BASE_URL/appointments/1/cancel" \
  -H "Authorization: Bearer $TOKEN"
# HTTP/1.1 200 OK
# {"id":1,"pet_id":1,"vet_id":2,"start_at":"<inicio>Z","end_at":"<fin>Z","status":"cancelled"}
```

## Códigos de respuesta

| Código | Cuándo se devuelve |
| --- | --- |
| 200 | Consulta correcta, inicio de sesión correcto y cancelación correcta. |
| 201 | Cuenta, mascota o turno creados. |
| 401 | Falta el encabezado `Authorization`, el token es inválido o las credenciales no son correctas. |
| 403 | La operación requiere una cuenta de cliente, la mascota es de otro cliente o el usuario no puede cancelar ese turno. |
| 404 | La mascota, el veterinario o el turno no existen. |
| 409 | El correo ya está registrado, el veterinario ya tiene un turno en ese horario o el turno ya estaba cancelado. |
| 422 | Los datos no superaron la validación: rol o especie desconocida, contraseña de menos de 8 caracteres, fecha de nacimiento futura, inicio fuera del calendario o turno en el pasado. |

Todos los endpoints salvo `GET /health`, `POST /auth/register` y `POST /auth/login`
exigen la cabecera `Authorization: Bearer <token>`.

## Reglas de negocio

- **Cuentas**: el rol es `client` o `vet` y el correo es único. La contraseña tiene al
  menos 8 caracteres y se guarda con argon2.
- **Mascotas**: la especie es `dog`, `cat` u `other`; la fecha de nacimiento no puede ser
  futura. Cada cliente ve solo sus propias mascotas.
- **Turnos**: duran 30 minutos y arrancan en punto o y media, de lunes a sábado, entre
  las 09:00 y las 17:30 UTC (la última hora de inicio es a las 17:30). Un veterinario no
  puede tener dos turnos activos en el mismo horario. Solo un cliente agenda, y
  únicamente con mascotas propias.
- **Cancelación**: la puede hacer el cliente dueño de la mascota o el veterinario del
  turno. El horario cancelado queda libre y se puede volver a reservar.
