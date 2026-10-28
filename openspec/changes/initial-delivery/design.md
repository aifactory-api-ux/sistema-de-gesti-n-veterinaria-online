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
