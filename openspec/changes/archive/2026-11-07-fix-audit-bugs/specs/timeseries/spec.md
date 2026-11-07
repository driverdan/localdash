## MODIFIED Requirements

### Requirement: Observations window query
The system SHALL serve historical observations at `GET /api/v1/timeseries/observations` as a GeoJSON FeatureCollection, filterable by `source`, `category`, `bbox`, `start`, and `end`, ordered newest-first, with a `limit` defaulting to 5000, at least 1, and capped at 50000. Each feature's `geometry` SHALL be the observation's stored geometry serialized as-is (point or polygon), and `bbox` SHALL be evaluated as a PostGIS intersection against that geometry.

#### Scenario: Time-window query
- **WHEN** a client requests observations with `start` and `end` timestamps
- **THEN** only observations whose `observed_at` falls within the window are returned, newest first, up to `limit`

#### Scenario: Polygon observation serialized as a polygon feature
- **WHEN** the window contains an area source's observation
- **THEN** its feature `geometry` is the stored `Polygon`/`MultiPolygon`, not a point

#### Scenario: Limit is capped
- **WHEN** a client requests a `limit` greater than 50000
- **THEN** the API rejects the request with a validation error

#### Scenario: Non-positive limit is rejected
- **WHEN** a client requests a `limit` of 0 or a negative number
- **THEN** the API rejects the request with a `422` validation error rather than a server error

### Requirement: Manual source refresh
The system SHALL trigger one collection cycle for a source via `POST /api/v1/timeseries/sources/{key}/refresh` and return the run result `{source, status, error, count}`. Manual and scheduled collection cycles for the same source SHALL be serialized: a cycle that starts while another cycle for that source is running SHALL wait for it to finish rather than ingest concurrently. Cycles for different sources SHALL NOT block each other.

#### Scenario: Refreshing a known source
- **WHEN** a client posts to `/api/v1/timeseries/sources/{key}/refresh` for a registered collector
- **THEN** the collector runs one fetch/normalize/ingest cycle and the run result is returned

#### Scenario: Refreshing an unknown source
- **WHEN** a client posts a refresh for a key with no registered collector
- **THEN** the API responds `404`

#### Scenario: Manual refresh during a scheduled tick is serialized
- **WHEN** a manual refresh for a source is posted while that source's scheduled cycle is running
- **THEN** the manual cycle begins only after the scheduled cycle completes, so the two never
  ingest the same source concurrently
