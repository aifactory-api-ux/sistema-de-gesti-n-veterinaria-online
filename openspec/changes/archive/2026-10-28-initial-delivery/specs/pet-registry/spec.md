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
