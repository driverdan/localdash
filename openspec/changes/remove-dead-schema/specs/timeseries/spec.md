## MODIFIED Requirements

### Requirement: Source registry
The system SHALL list sources at `GET /api/v1/timeseries/sources`: one entry per source that has
recorded at least one collection run, including a source whose collector is no longer registered.
Each entry SHALL include the source's `key`, `name`, `enabled`, `poll_interval_seconds`, and
last-run telemetry (`last_run_at`, `last_status`, `last_error`, `last_count`). `enabled` SHALL be
`true` when a collector with that key is registered in the running app (that is, it was built
from its `*_enabled` setting and is being polled) and `false` otherwise; it SHALL NOT be read from
a stored flag. The response SHALL NOT include any per-source configuration blob.

#### Scenario: Listing sources
- **WHEN** a client requests `GET /api/v1/timeseries/sources`
- **THEN** every source that has recorded a run is returned with its `key`, `name`, `enabled`,
  `poll_interval_seconds`, and last-run telemetry

#### Scenario: Registered collector reports enabled
- **WHEN** a source has recorded a run and a collector with its key is registered in the running
  app
- **THEN** its entry reports `enabled: true`

#### Scenario: Source whose collector was disabled reports not enabled
- **WHEN** a source has recorded a run in the past but its collector is not registered in the
  running app (for example, its `*_enabled` setting was turned off)
- **THEN** its entry is still listed with its last-run telemetry and reports `enabled: false`
