# user-auth Specification

## Purpose
Permite que clientes y veterinarios se registren en la plataforma, obtengan un token JWT y que la API aplique un control uniforme de autenticación y de rol sobre el resto de los endpoints.

## Requirements

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
