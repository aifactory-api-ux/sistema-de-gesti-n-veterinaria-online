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
