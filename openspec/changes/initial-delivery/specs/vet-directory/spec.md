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
