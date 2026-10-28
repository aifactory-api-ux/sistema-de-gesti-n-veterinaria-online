# Spec Delta

## Purpose

Exposes the liveness state of the veterinary clinic backend so the internal team and any container orchestrator can confirm the API is up and serving traffic without authenticating.

## ADDED Requirements

### Requirement: Health endpoint reports the service status

The system SHALL expose `GET /health` as a public endpoint that requires no credentials, and SHALL answer every request with HTTP 200 and the JSON body `{"status": "ok"}`.

#### Scenario: Health check without credentials

- **WHEN** a client sends `GET /health` with no `Authorization` header
- **THEN** the system responds with HTTP 200
- **AND** the JSON body is exactly `{"status": "ok"}`

#### Scenario: Health check with an invalid token

- **WHEN** a client sends `GET /health` with an invalid or expired bearer token
- **THEN** the system still responds with HTTP 200
- **AND** the JSON body is exactly `{"status": "ok"}`
