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


<!-- specs/appointment-scheduling/spec.md -->
# Spec Delta

## Purpose

Owns the clinic's appointment calendar: which client, which pet, which veterinarian and which slot are reserved, and the rules that keep two bookings from landing on the same veterinarian at the same moment.

## ADDED Requirements

### Requirement: A client books an appointment

The system SHALL accept `POST /appointments` with a JSON body containing `pet_id`, `vet_id` and `start_at` from a client, SHALL reserve a slot of 30 minutes starting at `start_at`, and SHALL answer HTTP 201 with a JSON body containing `id`, `pet_id`, `vet_id`, `start_at`, `end_at` and `status` equal to `"scheduled"`.

#### Scenario: A client books an available slot

- **WHEN** a client who owns pet `1` sends `POST /appointments` with `{"pet_id": 1, "vet_id": 7, "start_at": "2026-01-05T09:00:00Z"}` and the veterinarian `7` has no appointment in that slot
- **THEN** the system responds with HTTP 201
- **AND** the JSON body contains `id`, `pet_id` equal to `1`, `vet_id` equal to `7` and `status` equal to `scheduled`
- **AND** `start_at` is `2026-01-05T09:00:00Z` and `end_at` is `2026-01-05T09:30:00Z`

### Requirement: Only clients can book appointments

The system SHALL answer HTTP 403 when `POST /appointments` is sent by an authenticated veterinarian, and SHALL NOT reserve the slot.

#### Scenario: A veterinarian tries to book an appointment

- **WHEN** a veterinarian sends `POST /appointments` with `{"pet_id": 1, "vet_id": 7, "start_at": "2026-01-05T09:00:00Z"}`
- **THEN** the system responds with HTTP 403
- **AND** no appointment is created

### Requirement: An appointment may only use a pet owned by the client

The system SHALL answer HTTP 403 when `POST /appointments` refers to a pet that exists but is owned by another client, and SHALL NOT reserve the slot.

#### Scenario: A client books a pet that belongs to somebody else

- **WHEN** a client sends `POST /appointments` with a `pet_id` registered by a different client
- **THEN** the system responds with HTTP 403
- **AND** no appointment is created

### Requirement: The pet and the veterinarian of an appointment must exist

The system SHALL answer HTTP 404 when `POST /appointments` refers to a `pet_id` that does not exist or to a `vet_id` that is not a registered veterinarian, and SHALL NOT reserve the slot.

#### Scenario: Book an appointment for an unknown pet

- **WHEN** a client sends `POST /appointments` with `{"pet_id": 999, "vet_id": 7, "start_at": "2026-01-05T09:00:00Z"}`
- **THEN** the system responds with HTTP 404

#### Scenario: Book an appointment for an unknown veterinarian

- **WHEN** a client sends `POST /appointments` with `{"pet_id": 1, "vet_id": 999, "start_at": "2026-01-05T09:00:00Z"}`
- **THEN** the system responds with HTTP 404

### Requirement: The start of an appointment must land on the 30 minute grid

The system SHALL parse `start_at` of `POST /appointments` as an ISO 8601 timestamp expressed in UTC and SHALL answer HTTP 422 when its minute is neither `00` nor `30`, or when it carries leftover seconds, so that every appointment starts exactly on the hour or on the half hour.

#### Scenario: Book an appointment at an off grid minute

- **WHEN** a client sends `POST /appointments` with `"start_at": "2026-01-05T09:15:00Z"`
- **THEN** the system responds with HTTP 422
- **AND** no appointment is created

#### Scenario: Book an appointment with leftover seconds

- **WHEN** a client sends `POST /appointments` with `"start_at": "2026-01-05T09:00:30Z"`
- **THEN** the system responds with HTTP 422
- **AND** no appointment is created

#### Scenario: Book an appointment on the half hour

- **WHEN** a client sends `POST /appointments` with `"start_at": "2026-01-05T09:30:00Z"`
- **THEN** the system responds with HTTP 201
- **AND** `end_at` is `2026-01-05T10:00:00Z`

### Requirement: The start of an appointment must fall inside the clinic's working window

The system SHALL answer HTTP 422 when the `start_at` of `POST /appointments` is not a Monday to Saturday, is earlier than 09:00 UTC, or is later than 17:30 UTC, so that the last appointment of the day ends at 18:00 UTC.

#### Scenario: Book an appointment on a Sunday

- **WHEN** a client sends `POST /appointments` with a `start_at` that falls on a Sunday, for example `2026-01-04T09:00:00Z`
- **THEN** the system responds with HTTP 422
- **AND** no appointment is created

#### Scenario: Book an appointment before opening time

- **WHEN** a client sends `POST /appointments` with `"start_at": "2026-01-05T08:30:00Z"`
- **THEN** the system responds with HTTP 422
- **AND** no appointment is created

#### Scenario: Book an appointment after the last start of the day

- **WHEN** a client sends `POST /appointments` with `"start_at": "2026-01-05T18:00:00Z"`
- **THEN** the system responds with HTTP 422
- **AND** no appointment is created

#### Scenario: Book the last appointment of the day

- **WHEN** a client sends `POST /appointments` with `"start_at": "2026-01-05T17:30:00Z"`
- **THEN** the system responds with HTTP 201
- **AND** `end_at` is `2026-01-05T18:00:00Z`

#### Scenario: Book an appointment on a Saturday

- **WHEN** a client sends `POST /appointments` with a `start_at` that falls on a Saturday inside the working window
- **THEN** the system responds with HTTP 201

### Requirement: The start of an appointment must not be in the past

The system SHALL answer HTTP 422 when the `start_at` of `POST /appointments` is earlier than the current moment, so that no appointment can be booked in the past.

#### Scenario: Book an appointment on a date that already passed

- **WHEN** a client sends `POST /appointments` with a `start_at` in the previous day
- **THEN** the system responds with HTTP 422
- **AND** no appointment is created

### Requirement: A veterinarian cannot hold two active appointments in the same slot

The system SHALL answer HTTP 409 when `POST /appointments` requests a slot that the veterinarian already holds in an appointment whose status is not `"cancelled"`, and SHALL NOT create the second appointment.

#### Scenario: Two clients book the same veterinarian at the same time

- **WHEN** a veterinarian `7` already has a `"scheduled"` appointment starting at `2026-01-05T09:00:00Z`
- **AND** another client sends `POST /appointments` with `{"pet_id": 2, "vet_id": 7, "start_at": "2026-01-05T09:00:00Z"}`
- **THEN** the system responds with HTTP 409
- **AND** the veterinarian keeps a single appointment in that slot

#### Scenario: Two veterinarians are booked at the same time

- **WHEN** a veterinarian `7` already has a `"scheduled"` appointment starting at `2026-01-05T09:00:00Z`
- **AND** a client sends `POST /appointments` with `{"pet_id": 2, "vet_id": 8, "start_at": "2026-01-05T09:00:00Z"}`
- **THEN** the system responds with HTTP 201

### Requirement: The appointment listing is scoped by the role of the caller

The system SHALL expose `GET /appointments` to any authenticated account and SHALL answer HTTP 200 with a JSON array of appointment objects, holding the appointments of the client's own pets for a client and the appointments where the caller is the veterinarian for a veterinarian.

#### Scenario: A client lists the appointments of their own pets

- **WHEN** two clients each own a pet and one of them sends `GET /appointments` with a valid bearer token
- **THEN** the system responds with HTTP 200
- **AND** the JSON array holds only the appointments of the pets registered by that client

#### Scenario: A veterinarian lists their own appointments

- **WHEN** a veterinarian sends `GET /appointments` with a valid bearer token
- **THEN** the system responds with HTTP 200
- **AND** the JSON array holds only the appointments where that account is the veterinarian

#### Scenario: Each listed appointment carries its booking data

- **WHEN** a client sends `GET /appointments` with a valid bearer token
- **AND** the client has at least one appointment
- **THEN** every entry of the JSON array contains `id`, `pet_id`, `vet_id`, `start_at`, `end_at` and `status`

### Requirement: The owner client or the veterinarian of the appointment may cancel it

The system SHALL answer HTTP 200 with the appointment object whose `status` is `"cancelled"` when `POST /appointments/{id}/cancel` is sent by the client who owns the pet of the appointment or by the veterinarian of the appointment, keeping the rest of the appointment unchanged.

#### Scenario: The owner client cancels an appointment

- **WHEN** the client who owns the pet of an appointment sends `POST /appointments/{id}/cancel`
- **THEN** the system responds with HTTP 200
- **AND** the JSON body contains `status` equal to `cancelled`
- **AND** `id`, `pet_id`, `vet_id`, `start_at` and `end_at` are the ones of the cancelled appointment

#### Scenario: The veterinarian of the appointment cancels it

- **WHEN** the veterinarian of an appointment sends `POST /appointments/{id}/cancel`
- **THEN** the system responds with HTTP 200
- **AND** the JSON body contains `status` equal to `cancelled`

#### Scenario: A user that owns neither the pet nor the appointment is refused

- **WHEN** a client that does not own the pet of an appointment sends `POST /appointments/{id}/cancel` for an appointment booked with another veterinarian
- **THEN** the system responds with HTTP 403
- **AND** the appointment keeps its status `scheduled`

### Requirement: Cancelling an appointment that is already cancelled conflicts

The system SHALL answer HTTP 409 when `POST /appointments/{id}/cancel` is sent for an appointment whose status is already `"cancelled"`, and SHALL answer HTTP 404 when no appointment exists for the given identifier.

#### Scenario: Cancelling twice

- **WHEN** an appointment with status `scheduled` is cancelled and the same identifier is cancelled again
- **THEN** the second request responds with HTTP 409
- **AND** the appointment keeps the status `cancelled`

#### Scenario: Cancelling an unknown appointment

- **WHEN** a client sends `POST /appointments/999/cancel`
- **THEN** the system responds with HTTP 404

### Requirement: A cancelled slot is released for a new booking

The system SHALL allow a slot whose only appointment has the status `"cancelled"` to be booked again, and SHALL treat the cancelled appointment as inactive when it looks for a conflict.

#### Scenario: Booking a slot that was cancelled before

- **WHEN** an appointment of veterinarian `7` starting at `2026-01-05T09:00:00Z` was cancelled
- **AND** a client sends `POST /appointments` with `{"pet_id": 2, "vet_id": 7, "start_at": "2026-01-05T09:00:00Z"}`
- **THEN** the system responds with HTTP 201
- **AND** the new appointment has the status `scheduled`


<!-- specs/container-delivery/spec.md -->
# Spec Delta

## Purpose

Ships the veterinary clinic backend as a self contained container setup so that the internal team can build and run the API together with its PostgreSQL database from the repository root without installing anything by hand.

## ADDED Requirements

### Requirement: The project builds and runs from the repository root with Docker

The system SHALL ship a `Dockerfile` at the repository root that builds an image running the FastAPI application, and SHALL ship a `docker-compose.yml` at the repository root that builds that image, starts it together with a PostgreSQL service, and connects the API to that database through a `DATABASE_URL`; every path copied into the image SHALL exist in the repository.

#### Scenario: The root Dockerfile builds the API image

- **WHEN** the `Dockerfile` at the repository root is inspected
- **THEN** every source path it copies exists in the repository
- **AND** the image it produces runs the FastAPI application as its default process

#### Scenario: The root compose file starts the API and the database

- **WHEN** the `docker-compose.yml` at the repository root is parsed
- **THEN** it defines an API service that is built from the root `Dockerfile`
- **AND** it defines a PostgreSQL service that the API service depends on

#### Scenario: The API reaches the database through DATABASE_URL

- **WHEN** the root `docker-compose.yml` is parsed
- **THEN** the API service receives a `DATABASE_URL` that points at the PostgreSQL service of that same compose file

#### Scenario: The database keeps its data between runs

- **WHEN** the root `docker-compose.yml` is parsed
- **THEN** the PostgreSQL service stores its data in a named volume

#### Scenario: The running API stores its data in PostgreSQL

- **WHEN** the API of the compose stack registers an account through `POST /auth/register` and the client logs in through `POST /auth/login`
- **THEN** the account is read from and written to the PostgreSQL database of that stack
- **AND** the account is still present after the API container is restarted


<!-- specs/pet-registry/spec.md -->
# Spec Delta

## Purpose

Owns the registry of the pets the clinic treats: which client each animal belongs to, and the data every appointment about that animal must refer to.

## ADDED Requirements

### Requirement: A client registers a pet

The system SHALL accept `POST /pets` with a JSON body containing `name`, `species` and `birth_date`, where `birth_date` is an ISO calendar date, SHALL attach the pet to the authenticated client as its owner, and SHALL answer HTTP 201 with a JSON body containing `id`, `name`, `species`, `birth_date` and `owner_id`.

#### Scenario: A client creates a pet

- **WHEN** a client sends `POST /pets` with `{"name": "Firulais", "species": "dog", "birth_date": "2021-03-15"}`
- **THEN** the system responds with HTTP 201
- **AND** the JSON body contains `id`, `name` equal to `Firulais`, `species` equal to `dog` and `birth_date` equal to `2021-03-15`
- **AND** `owner_id` is the identifier of the authenticated client

### Requirement: Only clients can register pets

The system SHALL answer HTTP 403 when `POST /pets` is sent by an authenticated veterinarian, and SHALL NOT create the pet.

#### Scenario: A veterinarian tries to create a pet

- **WHEN** a veterinarian sends `POST /pets` with `{"name": "Firulais", "species": "dog", "birth_date": "2021-03-15"}`
- **THEN** the system responds with HTTP 403
- **AND** the pet is not registered for any owner

### Requirement: The species of a pet is limited to dog, cat and other

The system SHALL validate the `species` field of `POST /pets` against the values `"dog"`, `"cat"` and `"other"` and SHALL answer HTTP 422 for any other value.

#### Scenario: Create a pet with an unsupported species

- **WHEN** a client sends `POST /pets` with `{"name": "Roco", "species": "hamster", "birth_date": "2021-03-15"}`
- **THEN** the system responds with HTTP 422
- **AND** the pet is not registered

#### Scenario: Create a pet with the species other

- **WHEN** a client sends `POST /pets` with `{"name": "Roco", "species": "other", "birth_date": "2021-03-15"}`
- **THEN** the system responds with HTTP 201
- **AND** the JSON body contains `species` equal to `other`

### Requirement: The birth date of a pet cannot be in the future

The system SHALL validate the `birth_date` field of `POST /pets` and SHALL answer HTTP 422 when the birth date is later than the current calendar date.

#### Scenario: Create a pet born tomorrow

- **WHEN** a client sends `POST /pets` with a `birth_date` equal to the day after the current date
- **THEN** the system responds with HTTP 422
- **AND** the pet is not registered

#### Scenario: Create a pet born today

- **WHEN** a client sends `POST /pets` with a `birth_date` equal to the current date
- **THEN** the system responds with HTTP 201

### Requirement: The pet listing is scoped to the authenticated client

The system SHALL expose `GET /pets` to any authenticated account and SHALL answer HTTP 200 with a JSON array holding only the pets whose `owner_id` is the identifier of the authenticated account.

#### Scenario: A client lists only their own pets

- **WHEN** two clients each registered a pet and one of them sends `GET /pets` with a valid bearer token
- **THEN** the system responds with HTTP 200
- **AND** the JSON array holds exactly the pets registered by that client

#### Scenario: A veterinarian lists pets

- **WHEN** a veterinarian sends `GET /pets` with a valid bearer token
- **THEN** the system responds with HTTP 200
- **AND** the JSON array is empty


<!-- specs/service-health/spec.md -->
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


<!-- specs/user-auth/spec.md -->
# Spec Delta

## Purpose

Owns the accounts of the clinic's users (clients and veterinarians), the credentials they authenticate with, and the rule that every endpoint other than health, registration and login refuses to serve an unauthenticated or badly signed request.

## ADDED Requirements

### Requirement: Registration creates a client or veterinarian account

The system SHALL register an account when `POST /auth/register` receives a JSON body with `email`, `password` and `role`, where `role` is either `"client"` or `"vet"`, SHALL persist it, and SHALL answer with HTTP 201 and a JSON body containing the account's `id`, `email` and `role`.

#### Scenario: Register a client

- **WHEN** a client sends `POST /auth/register` with `{"email": "ana@example.com", "password": "secreto123", "role": "client"}`
- **THEN** the system responds with HTTP 201
- **AND** the JSON body contains `id`, `email` equal to `ana@example.com` and `role` equal to `client`

#### Scenario: Register a veterinarian

- **WHEN** a client sends `POST /auth/register` with `{"email": "dra.solis@example.com", "password": "secreto123", "role": "vet"}`
- **THEN** the system responds with HTTP 201
- **AND** the JSON body contains `id`, `email` equal to `dra.solis@example.com` and `role` equal to `vet`

#### Scenario: Registration response never leaks the password

- **WHEN** a registration succeeds
- **THEN** the JSON body contains no `password` field and no password hash

### Requirement: Registration rejects a role outside client and vet

The system SHALL validate the `role` field of `POST /auth/register` and SHALL answer HTTP 422 when the role is neither `"client"` nor `"vet"`.

#### Scenario: Register with an unknown role

- **WHEN** a client sends `POST /auth/register` with `{"email": "admin@example.com", "password": "secreto123", "role": "admin"}`
- **THEN** the system responds with HTTP 422
- **AND** no account is created for that email

### Requirement: Registration rejects a password shorter than eight characters

The system SHALL validate the `password` field of `POST /auth/register` and SHALL answer HTTP 422 when the password has fewer than 8 characters, while accepting a password of exactly 8 characters.

#### Scenario: Register with a seven character password

- **WHEN** a client sends `POST /auth/register` with `{"email": "corto@example.com", "password": "1234567", "role": "client"}`
- **THEN** the system responds with HTTP 422
- **AND** no account is created for that email

#### Scenario: Register with an eight character password

- **WHEN** a client sends `POST /auth/register` with `{"email": "ocho@example.com", "password": "12345678", "role": "client"}`
- **THEN** the system responds with HTTP 201

### Requirement: Registration rejects a duplicated email

The system SHALL answer HTTP 409 when `POST /auth/register` receives an email that is already registered, and SHALL leave the existing account untouched.

#### Scenario: Register the same email twice

- **WHEN** an account is registered with `{"email": "ana@example.com", "password": "secreto123", "role": "client"}`
- **AND** `POST /auth/register` is sent again with `{"email": "ana@example.com", "password": "otraclave", "role": "vet"}`
- **THEN** the second request responds with HTTP 409
- **AND** the existing account keeps its original role `client` and its original password

### Requirement: Login returns a bearer access token

The system SHALL answer `POST /auth/login` with HTTP 200 and a JSON body containing `access_token` and `token_type` equal to `"bearer"` when the credentials match an existing account, and SHALL issue the `access_token` as a signed JSON Web Token that carries the account's identity and role.

#### Scenario: Login with valid credentials

- **WHEN** a client sends `POST /auth/login` with `{"email": "ana@example.com", "password": "secreto123"}` for a registered account
- **THEN** the system responds with HTTP 200
- **AND** the JSON body contains `token_type` equal to `bearer`
- **AND** `access_token` is a JSON Web Token made of three dot separated segments

#### Scenario: Login token authenticates a protected endpoint

- **WHEN** a client logs in successfully and then sends `GET /vets` with the header `Authorization: Bearer <access_token>`
- **THEN** the system does not answer with HTTP 401
- **AND** the request is served as the account that logged in

### Requirement: Login rejects incorrect credentials

The system SHALL answer HTTP 401 when `POST /auth/login` receives a password that does not match the account, and SHALL answer HTTP 401 when no account exists for the submitted email.

#### Scenario: Login with a wrong password

- **WHEN** a client sends `POST /auth/login` with `{"email": "ana@example.com", "password": "incorrecta"}`
- **THEN** the system responds with HTTP 401

#### Scenario: Login with an unknown email

- **WHEN** a client sends `POST /auth/login` with `{"email": "nadie@example.com", "password": "secreto123"}`
- **THEN** the system responds with HTTP 401

### Requirement: Every other endpoint requires a valid bearer token

The system SHALL require an `Authorization: Bearer <access_token>` header on `GET /vets`, `POST /pets`, `GET /pets`, `POST /appointments`, `GET /appointments` and `POST /appointments/{id}/cancel`, and SHALL answer HTTP 401 when the header is absent, malformed, carries an invalid token, or carries a token whose signature does not verify.

#### Scenario: Protected endpoint without an Authorization header

- **WHEN** a client sends `GET /pets` with no `Authorization` header
- **THEN** the system responds with HTTP 401

#### Scenario: Protected endpoint with a malformed Authorization header

- **WHEN** a client sends `GET /appointments` with the header `Authorization: Basic abc123`
- **THEN** the system responds with HTTP 401

#### Scenario: Protected endpoint with an unknown token

- **WHEN** a client sends `GET /vets` with the header `Authorization: Bearer token.inventado`
- **THEN** the system responds with HTTP 401

#### Scenario: Protected endpoint with a token signed by another key

- **WHEN** a client sends `GET /pets` with a structurally valid bearer token signed with a different secret
- **THEN** the system responds with HTTP 401

#### Scenario: Public endpoints stay reachable without a token

- **WHEN** a client sends `GET /health`, `POST /auth/register` or `POST /auth/login` without an `Authorization` header
- **THEN** none of those requests is answered with HTTP 401

### Requirement: Passwords are stored as salted hashes

The system SHALL store only a salted hash of the submitted password, SHALL never store or return the plaintext password, and SHALL compare a login attempt against the stored hash.

#### Scenario: Stored credential differs from the submitted password

- **WHEN** an account is registered with the password `secreto123` and the persisted user record is inspected
- **THEN** the stored password value is not equal to `secreto123`

#### Scenario: Login is checked against the stored hash

- **WHEN** a client logs in with the correct email and the correct password
- **THEN** the system responds with HTTP 200


<!-- specs/vet-directory/spec.md -->
# Spec Delta

## Purpose

Publishes the directory of veterinarians available at the clinic so that a client who books an appointment can look up the identifier of the veterinarian to book with.

## ADDED Requirements

### Requirement: The veterinarian directory lists every veterinarian

The system SHALL expose `GET /vets` to any authenticated account and SHALL answer HTTP 200 with a JSON array holding one entry per account whose role is `"vet"`, where each entry contains that account's `id` and `email`.

#### Scenario: An authenticated client lists the veterinarians

- **WHEN** a client sends `GET /vets` with a valid bearer token and two veterinarian accounts exist
- **THEN** the system responds with HTTP 200
- **AND** the JSON body is an array with one entry per veterinarian
- **AND** each entry contains `id` and `email` and no other account data

#### Scenario: Only veterinarians are listed

- **WHEN** a client sends `GET /vets` with a valid bearer token while a client account also exists
- **THEN** the JSON array contains no entry for the client account

#### Scenario: The directory is empty when there are no veterinarians

- **WHEN** a client sends `GET /vets` with a valid bearer token and no veterinarian account exists
- **THEN** the system responds with HTTP 200
- **AND** the JSON body is an empty array


# Design

## Context

The repository is empty: no application code, no dependency manifest, no container files. The delivery must be a backend-only project (FastAPI + PostgreSQL) with an automated pytest suite that the internal clinic team can run without any external service, and it must also be runnable as containers from the repository root.

Two environment facts shape the approach:

- The delivery environment has no Docker daemon and no PostgreSQL server installed, so the automated test suite cannot depend on a running database container or a local PostgreSQL instance.
- The only consumer is the clinic's internal team, so the API is a single service with a small, well-known surface (ten endpoints) and no frontend, no external integration and no multi-tenant concern.

See `proposal.md` for the motivation and `specs/` for the behavior that is being implemented.

## Goals / Non-Goals

**Goals:**

- A layered FastAPI application that can be read endpoint by endpoint, with one router module per resource area.
- One persistence layer that speaks PostgreSQL in the delivered containers and a portable, dependency-free database in the test suite, without duplicating query code.
- Deterministic, timezone-safe handling of appointment instants, because every scheduling rule (grid, working window, past check) is an instant comparison.
- A container setup that starts the API and its database with a single command from the repository root.
- A test suite that runs with `pytest` alone, with no Docker daemon and no external service.

**Non-Goals:**

- No frontend, no admin panel, no email or SMS notifications, no payments, no file uploads.
- No refresh tokens, no password reset flow, no email verification, no rate limiting, no multi-tenant isolation.
- No schema migration tooling (Alembic) and no production seed data beyond what the API itself creates.
- No horizontal scaling, no caching layer, no message queue, no background scheduler.

## Decisions

### 1. Project layout

All application code lives in the `app/` package, all tests in `tests/`, and the container and documentation files at the repository root. Exact paths to create:

```
app/__init__.py
app/main.py
app/config.py
app/database.py
app/models.py
app/schemas.py
app/security.py
app/dependencies.py
app/routers/__init__.py
app/routers/health.py
app/routers/auth.py
app/routers/vets.py
app/routers/pets.py
app/routers/appointments.py
tests/__init__.py
tests/conftest.py
tests/test_health.py
tests/test_auth.py
tests/test_vets.py
tests/test_pets.py
tests/test_appointments.py
requirements.txt
requirements-dev.txt
pytest.ini
.env.example
.dockerignore
Dockerfile
docker-compose.yml
README.md
```

`app/main.py` builds the FastAPI application and includes one router per resource area; `app/routers/` holds only the HTTP concerns (path, status code, dependency wiring); `app/models.py` holds the SQLAlchemy tables; `app/schemas.py` holds the Pydantic request and response models; `app/security.py` holds password hashing and JWT issuing/verification; `app/dependencies.py` holds the reusable FastAPI dependencies (current user, client-only guard).

Alternative considered: a single `app/main.py` with every endpoint inline. Rejected because the ten endpoints plus the authorization rules would make one file the only place to look, and the security helpers would be tangled with the route bodies.

### 2. Synchronous SQLAlchemy 2.0 with psycopg 3

The data layer is SQLAlchemy 2.0 ORM (`DeclarativeBase`, `Mapped`, `mapped_column`) on a **synchronous** engine. The PostgreSQL URL is `postgresql+psycopg://...` (psycopg 3 driver) and the test URL is `sqlite://` (in-memory).

Rationale: the delivery environment has neither a Docker daemon nor a PostgreSQL server, so the suite must run against an embedded database; using one ORM and one URL scheme for both environments keeps a single set of queries and models, and the difference stays confined to `DATABASE_URL`. Sync SQLAlchemy also removes the need for `greenlet`/`asyncpg`/`aiosqlite` and lets every endpoint be a plain `def`, which is the simplest correct thing for a read/write workload of this size.

Alternatives considered: async SQLAlchemy with `asyncpg` (rejected: more moving parts and a second set of session semantics for no measurable benefit here); a raw `psycopg` repository layer without an ORM (rejected: hand-written SQL for three tables would duplicate the model's uniqueness and foreign-key guarantees); SQLite everywhere including production (rejected: the request mandates PostgreSQL).

### 3. Schema creation without a migration tool

`app/main.py` creates the tables on startup through `Base.metadata.create_all()`, and `app/database.py` exposes the engine and the session factory. The three tables are small and the delivery is the initial schema, so a migration tool would add a dependency and a directory of files that cannot be exercised in an environment without a PostgreSQL server.

Alternative considered: Alembic. Deferred to the first change that modifies an existing table; it would not alter any behavior in `specs/`.

### 4. Password hashing with argon2 and tokens with PyJWT

`app/security.py` hashes passwords with `argon2.PasswordHasher` (per-password salt, encoded hash) and issues HS256 JSON Web Tokens with PyJWT. The token payload carries the user identifier under `sub`, the role, an `iat` and an `exp`. `JWT_SECRET` and `ACCESS_TOKEN_EXPIRE_MINUTES` come from the environment through `app/config.py`; the secret has a development default that the container overrides.

Rationale: argon2 is memory-hard and needs no configuration; PyJWT is the smallest well-known JWT library and keeps signing and verification in one module. The password hash is never serialized into any response model, and the login check is `verify(hash, submitted_password)`.

Alternatives considered: `passlib` with bcrypt (rejected: `passlib` 1.7.4 against bcrypt 4.x emits a deprecation warning on every hash); unsalted SHA-256 (rejected: fast hashes are not password storage); opaque server-side sessions (rejected: the request asks for a JWT).

### 5. Authorization is expressed as dependencies, errors as explicit status codes

`app/dependencies.py` exposes `get_current_user` (parses the bearer token, resolves the user, raises 401) and `require_client` (calls `get_current_user` and raises 403 when the role is `vet`). Routers use `require_client` on `POST /pets` and `POST /appointments`; ownership rules compare the pet's `owner_id` with the authenticated user id and raise 403; the appointment cancel endpoint accepts either the owning client or the appointment's veterinarian and raises 403 otherwise.

Rationale: role and ownership checks are then written once, and every rejection carries the exact status code the specs require. Domain errors are raised as `HTTPException` with explicit codes (401, 403, 404, 409, 422) instead of being derived from exception handlers, because the requested status codes are part of the contract.

Alternative considered: a global exception handler that maps domain exceptions to status codes. Rejected because the mapping would live away from the rule that produced it.

### 6. Validation lives in the Pydantic schemas, scheduling rules in the service layer

`app/schemas.py` declares the request models: `role` is `Literal["client", "vet"]`, `species` is `Literal["dog", "cat", "other"]`, `password` has a minimum length of 8, and `birth_date` is a `date` with a field validator that rejects a date after today. The response models pin the exact JSON keys (`id`, `email`, `role`; `id`, `name`, `species`, `birth_date`, `owner_id`; `id`, `pet_id`, `vet_id`, `start_at`, `end_at`, `status`).

The appointment rules that need the database (pet exists, pet owned by the caller, veterinarian exists, slot free) and the rules that need the clock (past check) live in `app/routers/appointments.py` next to the endpoint, because they need the session and the current time. Pure calendar rules (minute in `{0, 30}`, second is zero, weekday Monday to Saturday, start between 09:00 and 17:30 UTC) are expressed as a small helper in the same module.

Alternative considered: putting the slot rules into `app/schemas.py` as a Pydantic validator. Rejected for the past-date rule, because "now" inside a schema validator is hidden from the reader; keeping all scheduling rules in one module makes the calendar rules auditable in one place.

### 7. One time representation: aware UTC everywhere, `UtcDateTime` at the column

`app/models.py` stores appointment instants in columns wrapped in a `UtcDateTime` type decorator: it converts an aware datetime to UTC and stores it naive, and re-attaches `tzinfo=UTC` when reading. Every comparison (grid, window, past, conflict) is done on aware UTC values, and the API always renders instants as UTC ISO 8601 with a `Z` suffix.

Rationale: SQLite does not keep timezone information, so a bare `DateTime(timezone=True)` column would return naive values in the test environment and aware values in PostgreSQL. The decorator makes both environments behave the same, which is what lets the suite assert on instants without special cases.

A `start_at` without an explicit offset is read as UTC, and a `start_at` with an explicit offset is converted to UTC before the rules are applied.

Alternative considered: storing the instant as an ISO 8601 string. Rejected because it loses ordering and range semantics in SQL.

### 8. Slot conflicts are detected by a query inside the booking transaction

Before inserting an appointment, `app/routers/appointments.py` queries the appointments of the requested veterinarian that start at the same instant and are not `cancelled`; if one exists it raises 409. Cancelled rows are therefore ignored, which is exactly the "a cancelled slot is free again" rule.

Alternative considered: a unique index on `(vet_id, start_at)`. Rejected because it would also forbid re-booking a cancelled slot, and because a partial unique index (`WHERE status <> 'cancelled'`) is not portable to the SQLite engine the test suite uses.

### 9. The container setup is a root Dockerfile plus a root compose file

`Dockerfile` uses a `python:3.11-slim` base, installs `requirements.txt`, copies `app/`, and starts `uvicorn app.main:app --host 0.0.0.0 --port 8000` as its default command. `docker-compose.yml` defines two services: `api`, built from the root `Dockerfile` with the database URL injected as `DATABASE_URL`, depending on `db`; and `db`, a `postgres:16-alpine` service with a named volume for its data directory. `.dockerignore` keeps `.venv`, `__pycache__`, `tests` and local caches out of the build context.

Rationale: the two files at the root are the ones a team member expects, and the compose file is the only place where the PostgreSQL credentials live.

Alternative considered: running the API on the host and only the database in a container. Rejected: the request is for a project that builds and runs containerized.

### 10. The test suite runs on an embedded database with no Docker

`tests/conftest.py` builds the application with `DATABASE_URL` pointed at an in-memory SQLite database, creates the schema once per test session, gives each test a clean set of tables, and provides helpers that register a client, register a veterinarian, log in and obtain a bearer header. The endpoints are exercised through FastAPI's `TestClient`, and the appointment tests use instants built relative to the current date so they do not rot.

Alternative considered: running the suite against the PostgreSQL service of the compose file. Rejected because it would require a Docker daemon in the delivery environment; the same suite can still be pointed at PostgreSQL by exporting `DATABASE_URL` before running `pytest`.

## Risks / Trade-offs

- [The test database is not PostgreSQL] → the models, queries and constraints are kept portable, and the UTC handling is centralised in `UtcDateTime` so both engines behave identically; the team can re-run the suite against PostgreSQL by setting `DATABASE_URL`.
- [Two clients can book the same slot at the same instant] → the conflict check and the insert run inside one transaction, and a database level guarantee (a filtered unique index) is the documented follow-up when the API is exposed beyond the internal team.
- [A client sends a local time without an offset] → the API reads such a value as UTC and rejects the ones that fall outside the working window with 422; the README documents that `start_at` must be UTC ISO 8601.
- [The container files cannot be built in the delivery environment] → `Dockerfile` and `docker-compose.yml` are verified statically (the compose file parses as YAML, every copied path exists in the repository, the service wiring and the `DATABASE_URL` point at each other), and the team builds them where a Docker daemon is available.
- [The JWT secret has a development default] → `app/config.py` reads `JWT_SECRET` from the environment and `docker-compose.yml` sets it, so the delivered containers never rely on the default.

## Migration Plan

Greenfield delivery, so there is no data to migrate and no rollback to plan beyond removing the containers and the volume. The order of deployment is: build the image, start `db`, start `api`, then confirm `GET /health` answers `200 {"status": "ok"}` and that the first registration can be created and logged into.

## Open Questions

- The default access token lifetime (`ACCESS_TOKEN_EXPIRE_MINUTES`) is a value the clinic can tune later; it does not change any behavior stated in `specs/`.
- Whether to add Alembic migrations and a filtered unique index for slot exclusivity is deferred until a first change alters the schema or the API leaves the internal team.
