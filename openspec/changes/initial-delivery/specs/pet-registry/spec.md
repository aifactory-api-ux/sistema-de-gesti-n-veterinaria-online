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
