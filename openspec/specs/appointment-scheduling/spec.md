# appointment-scheduling Specification

## Purpose
Permite que los clientes agenden turnos de 30 minutos con veterinarios concretos bajo reglas de agenda verificables, y que tanto el cliente como el veterinario puedan consultar y cancelar sus turnos.

## Requirements

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
