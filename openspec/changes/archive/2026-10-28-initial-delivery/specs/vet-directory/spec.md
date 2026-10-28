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
