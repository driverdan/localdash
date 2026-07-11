## ADDED Requirements

### Requirement: Entities collection
The system SHALL serve tracked entities at `GET /api/v1/timeseries/entities` as a GeoJSON FeatureCollection. The collection SHALL support the filters `active` (bool, default `true`), `source` (source key), `category`, `bbox` (`minLon,minLat,maxLon,maxLat`), and `closed_within` (minutes, 0–10080). Each feature's properties SHALL merge the entity's latest source properties with the authoritative keys `id`, `source`, `external_id`, `category`, `label`, `last_seen_at`, `active`, and `status` (reported as `Closed` for inactive entities).

#### Scenario: Default returns active entities only
- **WHEN** a client requests `GET /api/v1/timeseries/entities` with no parameters
- **THEN** the response is a GeoJSON FeatureCollection containing only entities with `is_active = true`

#### Scenario: Recently closed entities included via closed_within
- **WHEN** a client requests `GET /api/v1/timeseries/entities?closed_within=60`
- **THEN** the response contains active entities plus inactive entities last seen within the past 60 minutes, and each closed feature carries `active: false` and `status: "Closed"`

#### Scenario: Filtering by source, category, and bbox
- **WHEN** a client passes `source`, `category`, and/or `bbox` parameters
- **THEN** only entities matching every provided filter are returned, with `bbox` evaluated as a PostGIS intersection against the entity's last position

#### Scenario: Malformed bbox rejected
- **WHEN** a client passes a `bbox` that is not four comma-separated numbers
- **THEN** the API responds `400` with a message describing the expected `minLon,minLat,maxLon,maxLat` format

### Requirement: Entity detail snapshot
The system SHALL serve a single entity's current snapshot at `GET /api/v1/timeseries/entities/{id}`, including its identity (`id`, `source`, `external_id`, `category`, `label`), activity state (`is_active`, `first_seen_at`, `last_seen_at`), and `latest_properties`. The detail response SHALL NOT embed the observation track.

#### Scenario: Existing entity
- **WHEN** a client requests `GET /api/v1/timeseries/entities/{id}` for a known entity
- **THEN** the snapshot fields are returned without a `track` key

#### Scenario: Unknown entity
- **WHEN** a client requests an entity id that does not exist
- **THEN** the API responds `404`

### Requirement: Entity observation track
The system SHALL serve an entity's full observation history at `GET /api/v1/timeseries/entities/{id}/track`, ordered by `observed_at` ascending, where each item carries `observed_at`, `status`, `lon`, `lat`, and `properties`.

#### Scenario: Track for an entity with history
- **WHEN** a client requests the track of an entity that has recorded observations
- **THEN** the observations are returned oldest-first with position, status, and properties per point

#### Scenario: Track for unknown entity
- **WHEN** a client requests the track of an entity id that does not exist
- **THEN** the API responds `404`

### Requirement: Observations window query
The system SHALL serve historical observations at `GET /api/v1/timeseries/observations` as a GeoJSON FeatureCollection, filterable by `source`, `category`, `bbox`, `start`, and `end`, ordered newest-first, with a `limit` defaulting to 5000 and capped at 50000.

#### Scenario: Time-window query
- **WHEN** a client requests observations with `start` and `end` timestamps
- **THEN** only observations whose `observed_at` falls within the window are returned, newest first, up to `limit`

#### Scenario: Limit is capped
- **WHEN** a client requests a `limit` greater than 50000
- **THEN** the API rejects the request with a validation error

### Requirement: Source registry
The system SHALL list registered sources at `GET /api/v1/timeseries/sources`, including each source's `key`, `name`, `enabled`, `poll_interval_seconds`, and last-run telemetry (`last_run_at`, `last_status`, `last_error`, `last_count`).

#### Scenario: Listing sources
- **WHEN** a client requests `GET /api/v1/timeseries/sources`
- **THEN** every registered source is returned with its configuration and last-run telemetry

### Requirement: Manual source refresh
The system SHALL trigger one collection cycle for a source via `POST /api/v1/timeseries/sources/{key}/refresh` and return the resulting diff summary.

#### Scenario: Refreshing a known source
- **WHEN** a client posts to `/api/v1/timeseries/sources/{key}/refresh` for a registered collector
- **THEN** the collector runs one fetch/normalize/ingest cycle and the run result is returned

#### Scenario: Refreshing an unknown source
- **WHEN** a client posts a refresh for a key with no registered collector
- **THEN** the API responds `404`

### Requirement: Live diff WebSocket
The system SHALL expose a WebSocket at `/api/v1/timeseries/ws` that pushes each poll cycle's diff (`new` / `updated` / `closed` entities) to connected clients, with an optional `source` query parameter restricting the stream to one source.

#### Scenario: Receiving diffs
- **WHEN** a client is connected to `/api/v1/timeseries/ws` and a poll cycle produces changes
- **THEN** the client receives the diff so it can update its view incrementally

#### Scenario: Source-filtered stream
- **WHEN** a client connects with `?source=<key>`
- **THEN** it receives only diffs originating from that source

### Requirement: Retired flat routes
The legacy flat routes (`/api/active`, `/api/entities/{id}`, `/api/observations`, `/api/sources`, `/api/sources/{key}/refresh`, `/api/ws/live`) SHALL NOT be served. There are no redirects; the bundled frontend is updated in the same change.

#### Scenario: Old route returns 404
- **WHEN** a client requests `GET /api/active`
- **THEN** the API responds `404`
