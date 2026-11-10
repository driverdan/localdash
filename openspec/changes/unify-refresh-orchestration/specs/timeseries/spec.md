## MODIFIED Requirements

### Requirement: Manual source refresh
The system SHALL trigger one collection cycle for a source via `POST /api/v1/timeseries/sources/{key}/refresh` and return the run result `{source, status, error, count}`. The manual endpoint and the scheduled tick SHALL run the same collection cycle. That cycle collects, ingests, broadcasts a non-empty diff and records the source's last-run telemetry, so a manual refresh has the same effects as a scheduled one. Manual and scheduled collection cycles for the same source SHALL be serialized: a cycle that starts while another cycle for that source is running SHALL wait for it to finish rather than ingest concurrently. Cycles for different sources SHALL NOT block each other.

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

#### Scenario: Manual refresh records telemetry like a scheduled tick
- **WHEN** a manual refresh for a source completes, successfully or with a collector error
- **THEN** that source's `last_run_at`, `last_status`, `last_error` (redacted) and `last_count`
  are updated exactly as a scheduled tick would update them
