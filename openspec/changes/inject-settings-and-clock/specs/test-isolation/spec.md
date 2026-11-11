## MODIFIED Requirements

### Requirement: Tests do not depend on the date they run

A test's result SHALL NOT change as the calendar advances. A test that exercises behavior relative
to the current time (for example, the events reconciliation pass, which only considers events
starting at or after now) SHALL either compute its dates from the current time or pass a fixed
"now" into the code under test. Fixed calendar dates SHALL be used only where the code under test
does not compare them against the current time.

To make the fixed-"now" option available, every pipeline function that filters, ages, or stamps
stored data by the current time SHALL accept an optional keyword-only `now` argument (a
timezone-aware datetime). When `now` is omitted the function SHALL use the current UTC time, read
once per call, and SHALL use that single value for every comparison and stamp in the call. This
applies at least to `upsert_raw_events`, `run_sources`, `reconcile_events`, and
`retry_failed_geocodes` (events), `recluster` and `get_stories` (news), and the timeseries
`ingest`.

#### Scenario: Reconcile tests seed upcoming events

- **WHEN** a test seeds events for `reconcile_events()` to merge
- **THEN** the seeded start times are computed as a future offset from the current time, or the
  test passes a fixed `now` earlier than the seeded start times
- **AND** the test passes regardless of the date it runs on

#### Scenario: Time-independent tests keep fixed dates

- **WHEN** a test exercises code that never compares event dates to the current time (for example,
  `upsert_raw_events()` de-duplication)
- **THEN** the test may use fixed calendar dates, including dates in the past

#### Scenario: A fixed now decides which events reconciliation sees

- **WHEN** a test stores two duplicate events starting on a fixed past date and calls
  `reconcile_events(session, now=...)` with a `now` before that date
- **THEN** the pair is merged
- **AND** calling it with a `now` after that date merges nothing

#### Scenario: A fixed now decides which geocode failures are retried

- **WHEN** a test stores a failed geocode-cache row with a fixed `last_attempted_at` and calls
  `retry_failed_geocodes(..., retry_hours=24, now=...)` with `now` 25 hours after that stamp
- **THEN** the row is retried and its `last_attempted_at` becomes that `now`
- **AND** with `now` 23 hours after the stamp the row is not retried

#### Scenario: Omitting now keeps wall-clock behavior

- **WHEN** production code calls one of these functions without `now`
- **THEN** it behaves as if called with the current UTC time

## ADDED Requirements

### Requirement: Tests pass configuration in rather than mutating global settings

Pipeline code (event ingest, reconciliation and geocode retry; news clustering and story building;
timeseries ingest; the weather service) SHALL receive the setting values it uses as arguments or at
construction, and SHALL NOT call `get_settings()` itself. API handlers SHALL receive settings
through the FastAPI dependency `Depends(get_settings)`. `get_settings()` SHALL be called only at
composition roots: the database module, the application module and its lifespan, the scheduler,
the per-feature refresh cycles, router dependencies, the log-redaction filter, the weather
service's default when it is constructed without settings, and the outbound HTTP factory's default
User-Agent.

A test that needs a non-default setting SHALL pass the value, or a `Settings` it builds itself
(without reading `.env`), into the code under test. Tests SHALL NOT change the cached `Settings`
instance's attributes, and SHALL NOT set environment variables and clear the `get_settings()` cache
to vary a setting, except when the code under test is itself a composition root that reads
`get_settings()` (for example, a refresh cycle or the log-redaction filter).

#### Scenario: Blocklist test passes the blocklist

- **WHEN** a test checks that a blocklisted tag is not attached at ingest
- **THEN** it passes the blocklist to `upsert_raw_events` as an argument
- **AND** the cached `Settings` instance is not modified

#### Scenario: Weather tests build their own settings

- **WHEN** a weather-service test needs an AirNow key set or cleared
- **THEN** it constructs the service with a `Settings` built for that test
- **AND** neither the environment nor the `get_settings()` cache is changed

#### Scenario: Handler called directly receives settings

- **WHEN** a test calls an API handler function directly instead of through HTTP
- **THEN** it passes the `settings` argument explicitly

#### Scenario: Redaction tests may still set the environment

- **WHEN** a test checks that the log-redaction filter masks a configured secret
- **THEN** it may set the environment variable and clear the `get_settings()` cache, because the
  filter is a composition root that reads the live process settings
