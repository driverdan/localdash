## MODIFIED Requirements

### Requirement: AirNow AQI upstream contract
The system SHALL source current air-quality observations from the AirNow API
(`www.airnowapi.org` current-observations-by-lat/lon endpoint) at the shared center coordinate
settings, gated by the `airnow_api_key` setting (env `AIRNOW_API_KEY`, default empty). With an
empty key the system SHALL make no AirNow requests and `aqi` SHALL be `null`. The AQI fetch
SHALL run within the same cache refresh as the NWS fetches and SHALL fail independently of
them: an AirNow failure (error status, network failure, or no usable observations) SHALL NOT
be treated as a refresh error and SHALL leave the NWS halves untouched, and a successful AQI
fetch SHALL NOT rescue a refresh in which both NWS fetches failed.

When a refresh does not produce a usable AQI, the system SHALL carry forward the AQI from the
most recent prior refresh that had one, provided that AQI's observation time is within a
configurable maximum age (`airnow_stale_minutes`, env `AIRNOW_STALE_MINUTES`, default 120). If
there is no prior AQI, or the most recent one is older than the maximum age, `aqi` SHALL be
`null`. This carry-forward SHALL apply to both on-demand and scheduled refreshes.

Shaping the AirNow response SHALL be a pure function of the payload, testable offline against a
fixture: the overall AQI SHALL be the entry with the maximum `AQI` value across reported
pollutants (the EPA convention, identifying the primary pollutant), entries with missing or
negative AQI values SHALL be skipped, and an empty or all-invalid response SHALL yield `null`.
The shaped `aqi` object SHALL include an `observed_at` timestamp derived from the winning
entry's AirNow `DateObserved`/`HourObserved` fields, so its age can be bounded and displayed.

#### Scenario: AQI disabled by empty key
- **WHEN** `airnow_api_key` is empty and the weather cache refreshes
- **THEN** no request is made to AirNow and the payload carries `aqi: null`

#### Scenario: Overall AQI is the worst pollutant
- **WHEN** AirNow reports O3 at AQI 41 and PM2.5 at AQI 62
- **THEN** `aqi` carries value 62 with PM2.5 as the pollutant and PM2.5's category

#### Scenario: Shaped AQI carries its observation time
- **WHEN** the AirNow shaping function is given a recorded fixture payload with `DateObserved`
  and `HourObserved` on the winning entry
- **THEN** the shaped `aqi` object includes an `observed_at` timestamp for that observation

#### Scenario: Last-good AQI is carried forward on AirNow failure
- **WHEN** a prior refresh produced an AQI whose observation is within `airnow_stale_minutes`,
  and a later refresh's AirNow fetch fails or returns no usable observations while the NWS
  fetches succeed
- **THEN** the payload carries the NWS conditions and periods together with the prior AQI (its
  `observed_at` unchanged), and the refresh is not treated as an error

#### Scenario: Stale AQI is dropped past the maximum age
- **WHEN** the most recent AQI's observation is older than `airnow_stale_minutes` and the
  current AirNow fetch produces no usable AQI
- **THEN** the payload carries `aqi: null`

#### Scenario: AirNow failure with no prior AQI yields null
- **WHEN** the AirNow request fails during a refresh in which the NWS fetches succeed and no
  prior AQI has ever been cached
- **THEN** the payload carries the NWS conditions and periods with `aqi: null`, and the refresh
  is not treated as an error

#### Scenario: AQI success does not rescue a failed refresh
- **WHEN** both NWS fetches fail during a cold refresh and the AirNow fetch succeeds
- **THEN** the refresh is treated as failed (the endpoint returns 502 with no cached payload)

#### Scenario: AirNow shaping is testable offline
- **WHEN** the AirNow shaping function is given a recorded fixture payload
- **THEN** it produces the documented `aqi` shape with no network access
