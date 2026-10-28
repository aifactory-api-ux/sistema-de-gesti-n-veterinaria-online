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


<!-- specs/appointment-scheduling/spec.md -->
# Spec Delta

## Purpose

Permite que los clientes agenden turnos de 30 minutos con veterinarios concretos bajo reglas de agenda verificables, y que tanto el cliente como el veterinario puedan consultar y cancelar sus turnos.

## ADDED Requirements

### Requirement: Reserva de turno para una mascota propia
El sistema SHALL permitir que un cliente agende un turno mediante `POST /appointments` con `{"pet_id": ..., "vet_id": ..., "start_at": ...}` y SHALL responder con código `201` y cuerpo `{"id": ..., "pet_id": ..., "vet_id": ..., "start_at": ..., "end_at": ..., "status": "scheduled"}`.

#### Scenario: Turno válido agendado
- **WHEN** el cliente `ana@example.com` con la mascota `Firulais` (`id` = 1) agenda un turno con el veterinario `dra.luz@example.com` (`id` = 2) para el próximo lunes a las `09:00:00` UTC
- **THEN** la API responde con código `201` y el cuerpo JSON contiene las claves `id`, `pet_id`, `vet_id`, `start_at`, `end_at` y `status`, con `pet_id` igual a `1`, `vet_id` igual a `2` y `status` igual a `scheduled`

#### Scenario: El turno creado queda asociado a la mascota y al veterinario
- **WHEN** un turno se agenda correctamente
- **THEN** el turno persistido referencia el `pet_id` recibido, el `vet_id` recibido y el `owner_id` de la mascota

### Requirement: Duración fija de 30 minutos
Todo turno SHALL tener una duración exacta de 30 minutos, de modo que `end_at` sea `start_at` desplazado 30 minutos.

#### Scenario: Cálculo de la hora de fin
- **WHEN** se agenda un turno con `start_at` igual a `2027-03-01T09:00:00+00:00` o, en cualquier lunes futuro, a las `09:00:00` UTC
- **THEN** la respuesta `201` contiene `end_at` exactamente 30 minutos después, es decir a las `09:30:00` UTC del mismo día

### Requirement: Días de agenda de lunes a sábado
El sistema SHALL aceptar turnos solo de lunes a sábado (UTC) y SHALL responder con código HTTP `422` cuando `start_at` caiga en domingo.

#### Scenario: Turno en domingo
- **WHEN** se agenda un turno para el próximo domingo a las `09:00:00` UTC
- **THEN** la API responde con código `422` y no se crea el turno

#### Scenario: Turno en sábado
- **WHEN** se agenda un turno para el próximo sábado a las `10:00:00` UTC
- **THEN** la API responde con código `201`

### Requirement: Ventana horaria de 09:00 a 18:00
El sistema SHALL aceptar turnos cuyo inicio esté entre las `09:00:00` y las `17:30:00` UTC (de modo que el turno termine antes de las `18:00:00` UTC) y SHALL responder con código HTTP `422` para cualquier inicio fuera de esa ventana.

#### Scenario: Inicio antes de las 09:00
- **WHEN** se agenda un turno para el próximo lunes a las `08:30:00` UTC
- **THEN** la API responde con código `422` y no se crea el turno

#### Scenario: Inicio a las 17:30, último inicio permitido
- **WHEN** se agenda un turno para el próximo lunes a las `17:30:00` UTC
- **THEN** la API responde con código `201` y `end_at` es el mismo día a las `18:00:00` UTC

#### Scenario: Inicio después de las 17:30
- **WHEN** se agenda un turno para el próximo lunes a las `18:00:00` UTC
- **THEN** la API responde con código `422` y no se crea el turno

### Requirement: Minutos de inicio en punto o y media
El sistema SHALL exigir que los minutos de `start_at` sean `00` o `30` y SHALL responder con código HTTP `422` ante cualquier otro valor de minutos.

#### Scenario: Minutos no alineados a la media hora
- **WHEN** se agenda un turno para el próximo lunes a las `09:15:00` UTC
- **THEN** la API responde con código `422` y no se crea el turno

#### Scenario: Inicio a y media hora
- **WHEN** se agenda un turno para el próximo lunes a las `09:30:00` UTC
- **THEN** la API responde con código `201` y `end_at` es el mismo día a las `10:00:00` UTC

### Requirement: Formato ISO 8601 en UTC para start_at
El sistema SHALL aceptar `start_at` en formato ISO 8601 y SHALL interpretarlo y devolverlo en UTC.

#### Scenario: Entrada con desplazamiento horario
- **WHEN** se agenda un turno con `start_at` igual a `2027-03-01T11:00:00+02:00` o, en cualquier lunes futuro, a las `11:00:00+02:00`
- **THEN** la API responde con código `201` y devuelve `start_at` en UTC equivalente a las `09:00:00+00:00` de ese mismo día

#### Scenario: Entrada sin zona horaria
- **WHEN** se agenda un turno con `start_at` igual a `2027-03-01T09:00:00` sin desplazamiento o, en cualquier lunes futuro, a las `09:00:00` sin desplazamiento
- **THEN** la API responde con código `201` y devuelve `start_at` en UTC a las `09:00:00+00:00` de ese mismo día

#### Scenario: Entrada que no es una fecha ISO 8601
- **WHEN** se agenda un turno con `start_at` igual a `mañana a las 9`
- **THEN** la API responde con código `422` y no se crea el turno

### Requirement: El turno no puede estar en el pasado
El sistema SHALL responder con código HTTP `422` cuando `start_at` sea anterior o igual al instante actual en UTC.

#### Scenario: Fecha ya pasada
- **WHEN** se agenda un turno con `start_at` igual a `2020-01-01T09:00:00+00:00`
- **THEN** la API responde con código `422` y no se crea el turno

### Requirement: Mascota o veterinario inexistente
El sistema SHALL responder con código HTTP `404` cuando el `pet_id` o el `vet_id` no correspondan a un registro existente.

#### Scenario: Mascota inexistente
- **WHEN** se agenda un turno con `pet_id` igual a `999999` y un `vet_id` existente
- **THEN** la API responde con código `404` y no se crea el turno

#### Scenario: Veterinario inexistente
- **WHEN** se agenda un turno con un `pet_id` propio y `vet_id` igual a `999999`
- **THEN** la API responde con código `404` y no se crea el turno

### Requirement: Solo el dueño de la mascota puede agendar
El sistema SHALL responder con código HTTP `403` cuando el cliente intente agendar un turno para una mascota que no le pertenece.

#### Scenario: Mascota ajena
- **WHEN** el cliente `bruno@example.com` agenda un turno con el `pet_id` de la mascota `Firulais`, que pertenece a `ana@example.com`
- **THEN** la API responde con código `403` y no se crea el turno

### Requirement: Solo los clientes agendan turnos
El endpoint `POST /appointments` SHALL responder con código HTTP `403` cuando el portador del token tiene rol `vet`.

#### Scenario: Veterinario como cliente de un turno
- **WHEN** un token de rol `vet` se usa en `POST /appointments` con un cuerpo válido
- **THEN** la API responde con código `403` y no se crea el turno

### Requirement: Conflicto de horario del veterinario
El sistema SHALL responder con código HTTP `409` cuando el veterinario ya tenga un turno activo que se solape con el horario solicitado.

#### Scenario: El veterinario ya tiene un turno en ese horario
- **WHEN** `dra.luz@example.com` ya tiene un turno activo el próximo lunes de `09:00:00` a `09:30:00` UTC y otro cliente agenda un turno para ese mismo veterinary en el mismo horario
- **THEN** la API responde con código `409` y no se crea el segundo turno

#### Scenario: El conflicto afecta a cualquier cliente
- **WHEN** el veterinario ya tiene un turno activo en el horario y el turno duplicado lo agenda el mismo cliente con otra de sus mascotas
- **THEN** la API responde con código `409` y no se crea el turno duplicado

#### Scenario: Horarios distintos no entran en conflicto
- **WHEN** `dra.luz@example.com` tiene un turno activo de `09:00:00` a `09:30:00` UTC y se agenda otro turno con ella el mismo día a las `10:00:00` UTC
- **THEN** la API responde con código `201`

### Requirement: Listado de turnos según el rol
El endpoint `GET /appointments` SHALL devolver al cliente los turnos de sus propias mascotas y al veterinario los turnos que tiene asignados.

#### Scenario: El cliente ve los turnos de sus mascotas
- **WHEN** `ana@example.com` tiene un turno con `Firulais` y `bruno@example.com` tiene un turno con su mascota, y `ana@example.com` envía `GET /appointments`
- **THEN** la API responde con código `200` y el arreglo contiene únicamente el turno de la mascota de `ana@example.com`

#### Scenario: El veterinario ve sus turnos
- **WHEN** `dra.luz@example.com` tiene dos turnos asignados y `ana@example.com` tiene un turno con ella, y `dra.luz@example.com` envía `GET /appointments`
- **THEN** la API responde con código `200` y el arreglo contiene los dos turnos asignados a `dra.luz@example.com`

#### Scenario: El listado exige autenticación
- **WHEN** se envía `GET /appointments` sin cabecera `Authorization`
- **THEN** la API responde con código `401`

### Requirement: Cancelación autorizada del turno
El endpoint `POST /appointments/{id}/cancel` SHALL permitir cancelar el turno al cliente dueño de la mascota y al veterinario asignado, y SHALL responder con código HTTP `403` ante cualquier otro usuario.

#### Scenario: El dueño de la mascota cancela
- **WHEN** `ana@example.com` cancela un turno de su mascota `Firulais`
- **THEN** la API responde con código `200` y el turno devuelto tiene `status` igual a `cancelled`

#### Scenario: El veterinario asignado cancela
- **WHEN** `dra.luz@example.com` cancela un turno que tiene asignado
- **THEN** la API responde con código `200` y el turno devuelto tiene `status` igual a `cancelled`

#### Scenario: Usuario no relacionado intenta cancelar
- **WHEN** `bruno@example.com` cancela un turno de la mascota de `ana@example.com`
- **THEN** la API responde con código `403` y el turno conserva `status` igual a `scheduled`

#### Scenario: Turno inexistente
- **WHEN** se envía `POST /appointments/999999/cancel` con un token válido
- **THEN** la API responde con código `404`

### Requirement: No se cancela dos veces el mismo turno
El sistema SHALL responder con código HTTP `409` cuando se intente cancelar un turno que ya está cancelado.

#### Scenario: Segundo intento de cancelación
- **WHEN** un turno ya cancelado por `ana@example.com` es cancelado de nuevo por `ana@example.com`
- **THEN** la API responde con código `409` y el turno sigue con `status` igual a `cancelled`

### Requirement: El horario cancelado queda libre
Tras cancelar un turno, el mismo horario SHALL quedar disponible para agendar un nuevo turno con el mismo veterinario.

#### Scenario: Reagendar el horario cancelado
- **WHEN** `ana@example.com` cancela su turno del próximo lunes a las `09:00:00` UTC con `dra.luz@example.com` y a continuación agenda un nuevo turno para esa mascota en ese mismo horario
- **THEN** la API responde con código `201` y el nuevo turno tiene `status` igual a `scheduled`


<!-- specs/container-runtime/spec.md -->
# Spec Delta

## Purpose

Define la entrega containerizada del proyecto: una imagen de la API construida desde el `Dockerfile` de la raíz y una orquestación con `docker-compose.yml` en la raíz que levanta la API junto con PostgreSQL y ejecuta la suite de pruebas.

## ADDED Requirements

### Requirement: Dockerfile en la raíz del repositorio
El repositorio SHALL contener un archivo `Dockerfile` en su directorio raíz que construya una imagen con la API y sus dependencias, y que arranque el servidor HTTP de la aplicación.

#### Scenario: Construcción de la imagen de la API
- **WHEN** se ejecuta la construcción de la imagen a partir del `Dockerfile` de la raíz del repositorio
- **THEN** la construcción termina con código de salida `0` y produce una imagen que incluye el código de la aplicación y sus dependencias

#### Scenario: Arranque del servidor en la imagen
- **WHEN** se inicia un contenedor generado por ese `Dockerfile`
- **THEN** el proceso de la API queda escuchando en el puerto `8000` del contenedor

### Requirement: docker-compose.yml en la raíz del repositorio
El repositorio SHALL contener un archivo `docker-compose.yml` en su directorio raíz que defina un servicio de PostgreSQL y un servicio de la API, ambos construidos o levantados desde la raíz, de modo que el proyecto se ejecute con un único `docker compose up --build`.

#### Scenario: Levantamiento completo con Compose
- **WHEN** se ejecuta `docker compose up --build` desde la raíz del repositorio
- **THEN** los servicios de PostgreSQL y de la API se crean sin errores y la API queda accesible

#### Scenario: La API es alcanzable desde el host
- **WHEN** la orquestación está levantada y se consulta el endpoint `GET /health` publicado por el servicio de la API
- **THEN** la respuesta tiene código `200` y el cuerpo JSON `{"status": "ok"}`

#### Scenario: La API alcanza a PostgreSQL por el nombre del servicio
- **WHEN** el servicio de la API registra un usuario mediante `POST /auth/register` dentro de la red de Compose
- **THEN** la API responde con código `201` porque la base de datos del servicio de PostgreSQL está disponible

### Requirement: Persistencia de los datos de PostgreSQL
El servicio de PostgreSQL de Compose SHALL almacenar sus datos en un volumen persistente que sobrevive a la recreación del contenedor.

#### Scenario: Los datos sobreviven a la recreación del contenedor
- **WHEN** se registra un usuario a través de la API, se detiene y se vuelve a levantar la orquestación con `docker compose up --build`
- **THEN** el usuario sigue existiendo en PostgreSQL y un nuevo `POST /auth/login` con sus credenciales responde con código `200`

### Requirement: La suite de pruebas se ejecuta dentro de la imagen
La orquestación de Compose SHALL incluir un servicio capaz de ejecutar la suite de pruebas dentro de la imagen construida, y dicho servicio SHALL terminar con código de salida `0` cuando todas las pruebas pasan.

#### Scenario: Ejecución de las pruebas en contenedor
- **WHEN** se ejecuta `docker compose up --build --abort-on-container-exit --exit-code-from tests` desde la raíz del repositorio
- **THEN** el comando termina con código de salida `0` y el servicio de pruebas informa que todas las pruebas pasaron

#### Scenario: La suite usa PostgreSQL real
- **WHEN** el servicio de pruebas se ejecuta contra la base de datos PostgreSQL de la orquestación
- **THEN** las pruebas de persistencia, como el registro de un usuario y la creación de un turno, se ejecutan sin errores de conexión

### Requirement: Configuración por variables de entorno
La imagen de la API SHALL obtener su configuración (cadena de conexión a la base de datos, secreto de firma del token y puerto) de variables de entorno, y el `docker-compose.yml` SHALL proporcionarlas al servicio de la API sin incrustar secretos de producción en el repositorio.

#### Scenario: El servicio de la API recibe su configuración
- **WHEN** la orquestación levanta el servicio de la API
- **THEN** el servicio se inicia con una cadena de conexión válida y sirve peticiones HTTP

### Requirement: El contenedor no incluye el entorno de desarrollo
La imagen de la API SHALL incluir únicamente lo necesario para ejecutar la aplicación y SHALL exponer el puerto `8000`.

#### Scenario: La imagen expone el puerto de la aplicación
- **WHEN** se publica el puerto `8000` del contenedor de la API
- **THEN** las peticiones HTTP al puerto publicado son atendidas por la API del contenedor


<!-- specs/pet-registry/spec.md -->
# Spec Delta

## Purpose

Permite que cada cliente registre las mascotas que son de su propiedad y consulte su propio inventario, de modo que los turnos siempre puedan asociarse a una mascota real de quien agenda.

## ADDED Requirements

### Requirement: Registro de mascota por el cliente
El sistema SHALL permitir a un usuario con rol `client` registrar una mascota mediante `POST /pets` con el cuerpo `{"name": ..., "species": ..., "birth_date": ...}` y SHALL responder con código `201` y cuerpo `{"id": ..., "name": ..., "species": ..., "birth_date": ..., "owner_id": ...}`.

#### Scenario: Alta de mascota propia
- **WHEN** el cliente `ana@example.com` envía `POST /pets` con `{"name": "Firulais", "species": "dog", "birth_date": "2020-05-04"}`
- **THEN** la API responde con código `201` y el cuerpo JSON con las claves `id`, `name`, `species`, `birth_date` y `owner_id`, con `name` igual a `Firulais`, `species` igual a `dog`, `birth_date` igual a `2020-05-04` y `owner_id` igual al id del cliente `ana@example.com`

#### Scenario: El propietario no puede ser elegido por el cliente
- **WHEN** el cliente `ana@example.com` envía `POST /pets` con un cuerpo que incluye un `owner_id` distinto al suyo
- **THEN** la API responde con código `201` y el `owner_id` devuelto es el id del cliente `ana@example.com`

### Requirement: Especies permitidas
El sistema SHALL aceptar únicamente los valores de `species` `dog`, `cat` y `other`, y SHALL responder con código HTTP `422` ante cualquier otro valor.

#### Scenario: Especie no admitida
- **WHEN** se envía `POST /pets` con `{"name": "Paco", "species": "hamster", "birth_date": "2021-01-01"}`
- **THEN** la API responde con código `422` y no se registra la mascota `Paco`

#### Scenario: Especie `other` admitida
- **WHEN** se envía `POST /pets` con `{"name": "Paco", "species": "other", "birth_date": "2021-01-01"}`
- **THEN** la API responde con código `201` y el `species` devuelto es `other`

### Requirement: Fecha de nacimiento no futura
El sistema SHALL responder con código HTTP `422` cuando `birth_date` sea una fecha posterior a la fecha actual del servidor.

#### Scenario: Fecha de nacimiento en el futuro
- **WHEN** se envía `POST /pets` con `{"name": "Futura", "species": "cat", "birth_date": "2999-01-01"}`
- **THEN** la API responde con código `422` y no se registra la mascota `Futura`

#### Scenario: Fecha de nacimiento igual al día actual
- **WHEN** se envía `POST /pets` con `{"name": "Hoy", "species": "cat", "birth_date": "<fecha actual en UTC>"}`
- **THEN** la API responde con código `201`

### Requirement: Solo los clientes registran mascotas
El endpoint `POST /pets` SHALL responder con código HTTP `403` cuando el portador del token tiene rol `vet`.

#### Scenario: Veterinario intenta registrar una mascota
- **WHEN** un token de rol `vet` se usa en `POST /pets` con `{"name": "Rayo", "species": "dog", "birth_date": "2022-02-02"}`
- **THEN** la API responde con código `403` y no se registra la mascota `Rayo`

### Requirement: Listado acotado a las mascotas propias
El endpoint `GET /pets` SHALL devolver exclusivamente las mascotas cuyo `owner_id` es el usuario autenticado y SHALL responder con código `200` y un arreglo JSON de objetos de mascota.

#### Scenario: El cliente ve solo sus mascotas
- **WHEN** `ana@example.com` registra `Firulais` y `Luna`, existe además la mascota `Rayo` de `bruno@example.com`, y `ana@example.com` envía `GET /pets`
- **THEN** la API responde con código `200` y el arreglo contiene exactamente las mascotas `Firulais` y `Luna`

#### Scenario: Un cliente sin mascotas
- **WHEN** `bruno@example.com` no tiene mascotas y envía `GET /pets`
- **THEN** la API responde con código `200` con un arreglo JSON vacío `[]`

#### Scenario: El listado exige autenticación
- **WHEN** se envía `GET /pets` sin cabecera `Authorization`
- **THEN** la API responde con código `401`


<!-- specs/service-health/spec.md -->
# Spec Delta

## Purpose

Permite comprobar de forma rápida y sin autenticación que la API de la clínica veterinaria está en ejecución y responde correctamente, tanto desde fuera como desde la orquestación de contenedores.

## ADDED Requirements

### Requirement: Endpoint público de salud
El sistema SHALL exponer el endpoint `GET /health` sin exigir credenciales y SHALL responder con código HTTP `200` y cuerpo JSON `{"status": "ok"}`.

#### Scenario: Consulta de salud sin cabecera Authorization
- **WHEN** se envía una petición `GET /health` sin cabecera `Authorization`
- **THEN** la API responde con código `200` y el cuerpo JSON `{"status": "ok"}`

#### Scenario: Consulta de salud con token Bearer válido
- **WHEN** se envía una petición `GET /health` con la cabecera `Authorization: Bearer <token válido>`
- **THEN** la API responde con código `200` y el cuerpo JSON `{"status": "ok"}`

#### Scenario: El cuerpo de salud solo contiene el estado
- **WHEN** se consulta `GET /health`
- **THEN** el cuerpo JSON contiene la clave `status` con el valor `ok` y no expone información de base de datos ni de usuarios


<!-- specs/user-auth/spec.md -->
# Spec Delta

## Purpose

Permite que clientes y veterinarios se registren en la plataforma, obtengan un token JWT y que la API aplique un control uniforme de autenticación y de rol sobre el resto de los endpoints.

## ADDED Requirements

### Requirement: Alta de usuarios con rol client o vet
El sistema SHALL registrar usuarios mediante `POST /auth/register` con el cuerpo `{"email": ..., "password": ..., "role": ...}`, SHALL aceptar únicamente los roles `client` y `vet`, y SHALL responder con código `201` y cuerpo `{"id": ..., "email": ..., "role": ...}`.

#### Scenario: Registro exitoso de un cliente
- **WHEN** se envía `POST /auth/register` con `{"email": "ana@example.com", "password": "secreto123", "role": "client"}`
- **THEN** la API responde con código `201` y un cuerpo JSON con las claves `id`, `email` y `role` cuyo valor `email` es `ana@example.com` y cuyo valor `role` es `client`

#### Scenario: Registro exitoso de un veterinario
- **WHEN** se envía `POST /auth/register` con `{"email": "dra.luz@example.com", "password": "secreto123", "role": "vet"}`
- **THEN** la API responde con código `201` y un cuerpo JSON con las claves `id`, `email` y `role` cuyo valor `email` es `dra.luz@example.com` y cuyo valor `role` es `vet`

#### Scenario: El email se normaliza a minúsculas
- **WHEN** se envía `POST /auth/register` con `{"email": "Ana@Example.com", "password": "secreto123", "role": "client"}`
- **THEN** la API responde con código `201` y el `email` devuelto es `ana@example.com`

### Requirement: Email duplicado rechazado
El sistema SHALL responder con código HTTP `409` cuando el email registrado ya existe, sin crear un usuario adicional ni devolver el `id` de un usuario existente.

#### Scenario: Segundo registro con el mismo email
- **WHEN** ya existe el usuario `ana@example.com` y se envía `POST /auth/register` con `{"email": "ana@example.com", "password": "otraClave9", "role": "vet"}`
- **THEN** la API responde con código `409` y el número de usuarios con email `ana@example.com` sigue siendo uno

### Requirement: Contraseña mínima de 8 caracteres
El sistema SHALL rechazar con código HTTP `422` cualquier registro cuya contraseña tenga menos de 8 caracteres.

#### Scenario: Contraseña demasiado corta
- **WHEN** se envía `POST /auth/register` con `{"email": "corto@example.com", "password": "corta7", "role": "client"}` (6 caracteres)
- **THEN** la API responde con código `422` y no se crea el usuario `corto@example.com`

#### Scenario: Contraseña de exactamente 8 caracteres
- **WHEN** se envía `POST /auth/register` con `{"email": "ocho@example.com", "password": "12345678", "role": "client"}`
- **THEN** la API responde con código `201`

### Requirement: Rol inválido rechazado
El sistema SHALL responder con código HTTP `422` cuando el `role` no sea exactamente `client` ni `vet`.

#### Scenario: Rol fuera del catálogo
- **WHEN** se envía `POST /auth/register` con `{"email": "admin@example.com", "password": "secreto123", "role": "admin"}`
- **THEN** la API responde con código `422` y no se crea el usuario `admin@example.com`

#### Scenario: Rol ausente
- **WHEN** se envía `POST /auth/register` con `{"email": "sinrol@example.com", "password": "secreto123"}`
- **THEN** la API responde con código `422`

### Requirement: Emisión de token de acceso en el inicio de sesión
El sistema SHALL autenticar mediante `POST /auth/login` con `{"email": ..., "password": ...}` y SHALL responder con código `200` y cuerpo `{"access_token": ..., "token_type": "bearer"}` conteniendo un JWT firmado.

#### Scenario: Inicio de sesión con credenciales correctas
- **WHEN** se envía `POST /auth/login` con `{"email": "ana@example.com", "password": "secreto123"}` para un usuario existente
- **THEN** la API responde con código `200`, con `token_type` igual a `bearer` y con un `access_token` no vacío

#### Scenario: El token identifica al usuario y su rol
- **WHEN** se inicia sesión con las credenciales del veterinarian `dra.luz@example.com` y luego se usa el `access_token` devuelto en un endpoint protegido
- **THEN** la API reconoce al portador como el usuario `dra.luz@example.com` con rol `vet`

### Requirement: Credenciales incorrectas en el inicio de sesión
El sistema SHALL responder con código HTTP `401` cuando el email no exista o la contraseña no coincida, sin revelar cuál de los dos datos falló.

#### Scenario: Contraseña incorrecta
- **WHEN** se envía `POST /auth/login` con `{"email": "ana@example.com", "password": "claveMala1"}` para un usuario existente
- **THEN** la API responde con código `401` y no devuelve `access_token`

#### Scenario: Email inexistente
- **WHEN** se envía `POST /auth/login` con `{"email": "nadie@example.com", "password": "secreto123"}`
- **THEN** la API responde con código `401` y no devuelve `access_token`

### Requirement: Protección por Authorization Bearer
Todo endpoint distinto de `GET /health`, `POST /auth/register` y `POST /auth/login` SHALL exigir la cabecera `Authorization: Bearer <token>` y SHALL responder con código HTTP `401` si falta la cabecera, si el esquema no es `Bearer`, si el token es inválido o si el token ha expirado.

#### Scenario: Petición sin cabecera Authorization
- **WHEN** se envía `GET /pets` sin cabecera `Authorization`
- **THEN** la API responde con código `401`

#### Scenario: Token con firma inválida
- **WHEN** se envía `GET /pets` con la cabecera `Authorization: Bearer token.inventado.aaa`
- **THEN** la API responde con código `401`

#### Scenario: Token expirado
- **WHEN** se envía `GET /pets` con un `access_token` expirado en la cabecera `Authorization: Bearer`
- **THEN** la API responde con código `401`

#### Scenario: Esquema de autorización distinto de Bearer
- **WHEN** se envía `GET /pets` con la cabecera `Authorization: Basic dXNlcjpwYXNz`
- **THEN** la API responde con código `401`

#### Scenario: Petición con token válido
- **WHEN** se envía `GET /pets` con la cabecera `Authorization: Bearer <access_token de un cliente válido>`
- **THEN** la API NO responde con código `401` y procesa la consulta del cliente autenticado

### Requirement: Autorización por rol
Los endpoints reservados a clientes SHALL responder con código HTTP `403` cuando el portador del token tiene rol `vet`.

#### Scenario: Veterinario intenta registrar una mascota
- **WHEN** se envía `POST /pets` con `{"name": "Firulais", "species": "dog", "birth_date": "2020-05-04"}` usando un token de rol `vet`
- **THEN** la API responde con código `403` y no se crea la mascota

#### Scenario: Veterinario intenta agendar un turno
- **WHEN** se envía `POST /appointments` con un token de rol `vet` y un cuerpo válido
- **THEN** la API responde con código `403` y no se crea el turno

### Requirement: El material de la contraseña nunca se expone
Ninguna respuesta de la API SHALL incluir la contraseña en texto plano ni su valor derivado, y el sistema SHALL almacenar las contraseñas de forma irreversible (hash con sal).

#### Scenario: El registro no devuelve material de contraseña
- **WHEN** se registra un usuario correctamente con `POST /auth/register`
- **THEN** el cuerpo de la respuesta `201` no contiene las claves `password` ni `password_hash`

#### Scenario: El inicio de sesión no devuelve material de contraseña
- **WHEN** se inicia sesión correctamente con `POST /auth/login`
- **THEN** el cuerpo de la respuesta `200` no contiene las claves `password` ni `password_hash`


<!-- specs/vet-directory/spec.md -->
# Spec Delta

## Purpose

Permite que un cliente autenticado consulte el directorio de veterinarios disponibles para saber a quién puede agendar un turno.

## ADDED Requirements

### Requirement: Listado de veterinarios
El sistema SHALL exponer el endpoint `GET /vets` y SHALL responder con código `200` y un arreglo JSON de objetos `{"id": ..., "email": ...}`, uno por cada usuario con rol `vet`, sin incluir clientes ni campos adicionales.

#### Scenario: Directorio con veterinarios registrados
- **WHEN** existen los veterinarios `dra.luz@example.com` y `dr.carlos@example.com` y se envía `GET /vets` con un token válido
- **THEN** la API responde con código `200` y el arreglo contiene dos elementos con las claves `id` y `email` y con los emails `dra.luz@example.com` y `dr.carlos@example.com`

#### Scenario: Los clientes no aparecen en el directorio
- **WHEN** existe el cliente `ana@example.com` y se envía `GET /vets` con un token válido
- **THEN** la API responde con código `200` y ninguno de los elementos devueltos tiene el email `ana@example.com`

#### Scenario: Directorio sin veterinarios
- **WHEN** no existe ningún usuario con rol `vet` y se envía `GET /vets` con un token válido
- **THEN** la API responde con código `200` y con un arreglo JSON vacío `[]`

### Requirement: El directorio exige autenticación
El endpoint `GET /vets` SHALL exigir la cabecera `Authorization: Bearer <token>` y SHALL responder con código HTTP `401` cuando falte o sea inválida.

#### Scenario: Consulta del directorio sin token
- **WHEN** se envía `GET /vets` sin cabecera `Authorization`
- **THEN** la API responde con código `401`

#### Scenario: Consulta del directorio con token inválido
- **WHEN** se envía `GET /vets` con la cabecera `Authorization: Bearer token.inventado.aaa`
- **THEN** la API responde con código `401`


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
