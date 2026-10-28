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
