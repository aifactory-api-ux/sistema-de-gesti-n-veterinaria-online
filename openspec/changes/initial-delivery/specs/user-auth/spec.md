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
