# Proposal

## Why

The clinic has no software behind its front desk: pets, owners and appointment slots live in paper notebooks and phone calls, so nothing prevents two bookings for the same veterinarian at the same time and there is no single place to see the clinic's agenda. A single REST backend that owns accounts, pets and the appointment calendar removes that coordination cost and gives the internal team one place to work from.

## What Changes

- Add a REST API for the veterinary clinic backend, implemented with FastAPI and backed by PostgreSQL.
- Add JWT authentication: clients and veterinarians register with an email, a password and a role, log in for a bearer token, and every endpoint other than health, register and login requires that token.
- Add a veterinarian directory (`GET /vets`) so a client can pick who to book with.
- Add a pet registry (`POST /pets`, `GET /pets`) where each client records the pets they own, with a controlled species vocabulary and no future birth date.
- Add appointment scheduling (`POST /appointments`, `GET /appointments`, `POST /appointments/{id}/cancel`) with 30-minute slots on a fixed grid inside the clinic's working window, no double booking for a veterinarian, and cancellation by the owner or the veterinarian.
- Add a health endpoint (`GET /health`) for liveness checks.
- Add the containerized delivery of the project: a root `Dockerfile` and a root `docker-compose.yml` that build and run the API together with its PostgreSQL database.

## Capabilities

### New Capabilities

- `service-health`: liveness endpoint that reports whether the API is up.
- `user-auth`: registration, login and JWT bearer protection for every non-public endpoint.
- `vet-directory`: read-only listing of the veterinarians a client can book an appointment with.
- `pet-registry`: creation and per-owner listing of the pets a client has registered.
- `appointment-scheduling`: booking, per-role listing and cancellation of 30-minute clinic appointments.
- `container-delivery`: Dockerfile and root `docker-compose.yml` that build and run the project with its database.

### Modified Capabilities

None. The project has no capability specs yet, so this change only introduces new ones.

## Impact

- New backend project rooted at the repository root: `app/` (FastAPI application, routers, SQLAlchemy models, JWT security), `tests/` (pytest suite), `requirements.txt`, `Dockerfile`, `docker-compose.yml`, `.env.example` and `README.md`.
- New runtime dependencies: FastAPI, Uvicorn, SQLAlchemy 2, psycopg 3 (PostgreSQL driver), PyJWT, argon2-cffi, pydantic-settings, plus pytest and httpx for the test suite.
- New data model persisted in PostgreSQL: users (email, password hash, role), pets (name, species, birth date, owner) and appointments (pet, veterinarian, start, end, status).
- New public HTTP surface: `GET /health`, `POST /auth/register`, `POST /auth/login`, `GET /vets`, `POST /pets`, `GET /pets`, `POST /appointments`, `GET /appointments`, `POST /appointments/{id}/cancel`.
- No frontend, no third-party integration, no notification delivery and no deployment beyond the local container setup.
