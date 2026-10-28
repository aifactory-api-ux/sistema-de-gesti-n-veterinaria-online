# Proposal

## Why

La clínica veterinaria necesita una plataforma backend para que los clientes registran sus mascotas y agendan turnos con veterinarios de forma ordenada y verificable. Hoy no existe ninguna API: el flujo de registro, autenticación y reserva de turnos es manual, lo que impide confirmar la disponibilidad de un veterinario y deja al cliente sin garantía sobre sus citas.

Esta entrega introduce la primera versión funcional de esa plataforma, incluyendo autenticación JWT, catálogo de veterinarios, registro de mascotas y un sistema de turnos con reglas de agenda claras, más un README con ejemplos `curl` y una suite de pruebas automatizadas.

## What Changes

- Se agrega un endpoint público de salud `GET /health` que responde `200 {"status": "ok"}`.
- Se agrega `POST /auth/register` para crear usuarios con rol `client` o `vet`, con `201 {id, email, role}`, `409` ante email duplicado y `422` ante password menor a 8 caracteres o rol inválido.
- Se agrega `POST /auth/login` que emite un JWT (`200 {access_token, token_type: "bearer"}`) y responde `401` ante credenciales incorrectas.
- Se agrega protección por `Authorization: Bearer` en todos los endpoints salvo `GET /health`, `POST /auth/register` y `POST /auth/login`; sin token o con token inválido se responde `401`.
- Se agrega `GET /vets` que lista los veterinarios registrados como `[{id, email}]`.
- Se agrega `POST /pets` (solo clientes) con validación de `species` (`dog`, `cat`, `other`) y `birth_date` no futura, devolviendo `201 {id, name, species, birth_date, owner_id}`; se agrega `GET /pets` que devuelve únicamente las mascotas del cliente autenticado.
- Se agrega `POST /appointments` (solo clientes y solo con mascotas propias) que valida la ventana de agenda (lunes a sábado, 09:00–18:00, inicio en punto o y media, último inicio 17:30, duración 30 minutos, `start_at` en UTC ISO 8601 y nunca en pasado), responde `404` si la mascota o el veterinario no existen, `403` si la mascota es ajena y `409` si el veterinario ya tiene un turno activo en ese horario; devuelve `201 {id, pet_id, vet_id, start_at, end_at, status: "scheduled"}`.
- Se agrega `GET /appointments` que muestra al cliente los turnos de sus mascotas y al veterinario los turnos asignados a él.
- Se agrega `POST /appointments/{id}/cancel`, permitido al cliente dueño de la mascota o al veterinario del turno (`403` para terceros), que devuelve el turno con `status: "cancelled"`, responde `409` si ya estaba cancelado y libera el horario para volver a agendar.
- Se agrega el empaquetado containerizado del proyecto: `Dockerfile` en la raíz del repositorio y `docker-compose.yml` en la raíz del repositorio que levantan la API y su base de datos PostgreSQL.
- Se agrega una suite de pruebas con `pytest` y un `README.md` con instrucciones de arranque y ejemplos `curl`.

## Capabilities

### New Capabilities

- `service-health`: Exposición de un endpoint de salud público que permite a operadores y a la orquestación de contenedores comprobar que la API está viva.
- `user-auth`: Registro de usuarios con rol `client` o `vet`, emisión y validación de JWT, y aplicación uniforme de la protección `Authorization: Bearer` en el resto de la API.
- `vet-directory`: Consulta del directorio de veterinarios disponibles para que los clientes puedan elegir profesional al agendar.
- `pet-registry`: Registro de mascotas a nombre del cliente autenticado y listado acotado a las mascotas propias.
- `appointment-scheduling`: Reserva de turnos de 30 minutos con reglas de agenda y zona horaria, listado según el rol del usuario y cancelación con liberación del horario.
- `container-runtime`: Empaquetado y ejecución containerizada de la API y de su base de datos PostgreSQL mediante `Dockerfile` y `docker-compose.yml` en la raíz del repositorio.

### Modified Capabilities

Ninguna. No existen capacidades previas en `openspec/specs/`; la entrega es íntegramente nueva.

## Impact

- **Código nuevo**: API REST en FastAPI con capa de acceso a datos sobre PostgreSQL (SQLAlchemy 2.0), modelos de `users`, `pets` y `appointments`, y enrutadores para salud, autenticación, veterinarios, mascotas y turnos.
- **Dependencias nuevas**: FastAPI, Uvicorn, SQLAlchemy 2.0, driver PostgreSQL, PyJWT, biblioteca de hashing de contraseñas y dependencias de validación.
- **Contrato HTTP público**: los endpoints `GET /health`, `POST /auth/register`, `POST /auth/login`, `GET /vets`, `POST /pets`, `GET /pets`, `POST /appointments`, `GET /appointments` y `POST /appointments/{id}/cancel` con sus códigos de éxito y de error.
- **Infraestructura**: `Dockerfile` multi-etapa ligero en la raíz y `docker-compose.yml` en la raíz con servicios de API, PostgreSQL y ejecución de pruebas.
- **Documentación y calidad**: `README.md` con pasos de arranque y ejemplos `curl`, y suite `pytest` contra una base PostgreSQL real.
- **Fuera de alcance**: no se requieren integraciones de pago, notificaciones, frontend web, roles de administrador, multi-clínica, ni ficha de historial clínico, porque la solicitud original no los pide.
