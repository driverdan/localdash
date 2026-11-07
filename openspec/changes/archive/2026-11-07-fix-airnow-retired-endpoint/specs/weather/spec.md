## MODIFIED Requirements

### Requirement: AirNow AQI upstream contract
The system SHALL source current air-quality observations from the AirNow API
(`www.airnowapi.org` current-observations-by-latitude/longitude-or-ZIP endpoint,
`/aq/observation/current/ziplatlong/`) at the shared center coordinate settings, gated by the
`airnow_api_key` setting (env `AIRNOW_API_KEY`, default empty). With an empty key the system
SHALL make no AirNow requests and `aqi` SHALL be `null`. The AQI fetch SHALL run within the
same cache refresh as the NWS fetches and SHALL fail independently of them. An AirNow failure
SHALL NOT be treated as a refresh error and SHALL leave the NWS halves untouched. Failures
include an error status, a network failure, an AirNow `WebServiceError` envelope in place of
observations, and no usable observations. A successful AQI fetch SHALL NOT rescue a refresh
in which both NWS fetches failed.

When an AirNow fetch fails because of an error status or a `WebServiceError` envelope, the
logged warning SHALL include the HTTP status (for an error status) and the envelope's error
message text, if any. The log SHALL NOT contain the API key.

When a refresh does not produce a usable AQI, the system SHALL carry forward the AQI from the
most recent prior refresh that had one, provided that AQI's observation time is within a
configurable maximum age (`airnow_stale_minutes`, env `AIRNOW_STALE_MINUTES`, default 120). If
there is no prior AQI, or the most recent one is older than the maximum age, `aqi` SHALL be
`null`. This carry-forward SHALL apply to both on-demand and scheduled refreshes.

Shaping the AirNow response SHALL be a pure function of the payload, testable offline against
a fixture. The rules are:

- The overall AQI SHALL be the entry with the maximum `nowcastAQI` value across reported
  pollutants (the EPA convention, identifying the primary pollutant).
- Entries with missing, non-numeric, or negative `nowcastAQI` values SHALL be skipped.
- An empty, all-invalid, or non-list response (such as a `WebServiceError` envelope) SHALL
  yield `null`.
- The pollutant SHALL be the winning entry's `parameterName`, and the category name SHALL be
  its `aqiCategoryName`. Both SHALL be passed through verbatim.
- The category number SHALL be derived from the AQI value using the EPA breakpoints:
  0–50 → 1, 51–100 → 2, 101–150 → 3, 151–200 → 4, 201–300 → 5, above 300 → 6.
- The shaped `aqi` object SHALL include an `observed_at` timestamp derived from the winning
  entry's `dateObserved`, `hourObserved` (an `"HH:MM"` string), and `localTimeZone` fields, so
  its age can be bounded and displayed.

#### Scenario: AQI disabled by empty key
- **WHEN** `airnow_api_key` is empty and the weather cache refreshes
- **THEN** no request is made to AirNow and the payload carries `aqi: null`

#### Scenario: AQI is fetched from the current-observations endpoint
- **WHEN** `airnow_api_key` is set and the weather cache refreshes
- **THEN** the system requests `/aq/observation/current/ziplatlong/` with the center
  `latitude`/`longitude` and the key

#### Scenario: Overall AQI is the worst pollutant
- **WHEN** AirNow reports OZONE at `nowcastAQI` 41 and PM2.5 at `nowcastAQI` 62
- **THEN** `aqi` carries value 62 with PM2.5 as the pollutant and PM2.5's category

#### Scenario: Category number is derived from the AQI value
- **WHEN** the winning entry has `nowcastAQI` 62 and `aqiCategoryName` "Moderate"
- **THEN** `aqi` carries category 2 and category name "Moderate"

#### Scenario: Category breakpoints follow the EPA scale
- **WHEN** the winning entry's AQI value is 50, 51, 150, 151, 300, or 301
- **THEN** the derived category is 1, 2, 3, 4, 5, or 6 respectively

#### Scenario: Shaped AQI carries its observation time
- **WHEN** the AirNow shaping function is given a recorded fixture payload whose winning entry
  has `dateObserved` "2026-11-06", `hourObserved` "22:00", and `localTimeZone` "EST"
- **THEN** the shaped `aqi` object has `observed_at` "2026-11-06T22:00:00-05:00"

#### Scenario: No-observations envelope yields no AQI
- **WHEN** AirNow answers HTTP 200 with a `WebServiceError` envelope reporting no observations
  within range
- **THEN** the refresh's AQI is unusable (so carry-forward applies), the refresh is not treated
  as an error, and the logged warning includes AirNow's message

#### Scenario: Error status logs AirNow's message without the key
- **WHEN** AirNow answers HTTP 410 with a `WebServiceError` envelope whose message says the
  service has been retired
- **THEN** the logged warning includes the status 410 and that message, does not contain the
  API key, and the payload carries `aqi: null` when no prior AQI is cached

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
