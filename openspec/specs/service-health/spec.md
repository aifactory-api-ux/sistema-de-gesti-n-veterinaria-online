# service-health Specification

## Purpose
Permite comprobar de forma rápida y sin autenticación que la API de la clínica veterinaria está en ejecución y responde correctamente, tanto desde fuera como desde la orquestación de contenedores.

## Requirements

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
