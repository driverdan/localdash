# weather Specification

## Purpose

The backend weather feature: current conditions + today's forecast proxied from the National
Weather Service API (`api.weather.gov`) at the shared app-level center coordinate, served at
`/api/v1/weather/current` for the home page's weather strip, with AirNow air quality folded in
when an API key is configured. Deliberately stateless — no DB tables — an in-process TTL cache,
kept current by one scheduled refresh job, shields the browser from NWS's two-hop discovery,
User-Agent requirement, and slowness. Not a geo/timeseries source: weather does not
flow through collectors/ingest (weather-on-the-map remains a separate future idea).
## Requirements
### Requirement: Weather API namespace and current-conditions endpoint
The system SHALL serve weather under its own feature namespace `/api/v1/weather/` (one
`APIRouter` module composed in the application entrypoint, per the app-shell convention), gated
by a `weather_enabled` setting. `GET /api/v1/weather/current` SHALL return a single JSON object
with:

- `current`: the latest station observation — temperature in °F, text description, NWS icon URL,
  wind, relative humidity, and the **observation timestamp** — or `null` when no usable
  observation is available;
- `periods`: the first two NWS forecast periods, each carrying the NWS-assigned period name
  (e.g. "Today", "Tonight", "This Afternoon"), temperature and unit, precipitation probability,
  and short and detailed forecast text. Period names SHALL be passed through from NWS verbatim,
  never synthesized, because NWS renames the leading period through the day;
- `aqi`: the current overall air-quality index from AirNow — AQI value, EPA category number
  (1–6) and category name (passed through verbatim), and primary pollutant name — or `null`
  when AirNow is unconfigured, unreachable, or reports no usable observations.

#### Scenario: Fetching current weather
- **WHEN** a client requests `GET /api/v1/weather/current` and NWS is reachable
- **THEN** it receives `current` conditions with an observation timestamp and the first two
  forecast periods with their NWS period names

#### Scenario: Fetching current weather with AirNow configured
- **WHEN** a client requests `GET /api/v1/weather/current` with a non-empty `airnow_api_key`
  and AirNow reachable
- **THEN** the response's `aqi` object carries the AQI value, category number, category name,
  and primary pollutant

#### Scenario: Feature disabled by configuration
- **WHEN** the application starts with `weather_enabled` off
- **THEN** the weather router is not registered and `/api/v1/weather/current` returns 404, with
  no NWS requests made

### Requirement: NWS upstream contract
The system SHALL source weather from the National Weather Service API (`api.weather.gov`) using
the shared center coordinate settings (`center_lat`/`center_lon`). Gridpoint discovery
(`GET /points/{lat},{lon}`, yielding the forecast URL and observation-stations URL) SHALL be
resolved lazily on first use and cached for the process lifetime; a failed discovery SHALL NOT be
cached and SHALL be retried on the next request. Steady-state refreshes SHALL make exactly two
NWS calls: the gridpoint forecast, and the latest observation from the discovered station
list. All NWS requests SHALL send the application's configured `user_agent`. Observation
temperatures (reported by NWS in °C) SHALL be converted to °F; an observation with a null
temperature SHALL fall back to the next station in the discovered list, and `current` SHALL be
`null` if no station yields a usable observation.

#### Scenario: Discovery is resolved once per process
- **WHEN** multiple cache-expired requests are served over the life of one process
- **THEN** `GET /points/{lat},{lon}` is called at most once (on first use), and subsequent
  refreshes call only the forecast and observation endpoints (plus the AirNow fetch when
  configured)

#### Scenario: Identifying User-Agent on upstream requests
- **WHEN** any request is made to `api.weather.gov`
- **THEN** it carries the configured `user_agent` header value

#### Scenario: Null-temperature observation falls back
- **WHEN** the first station's latest observation reports a null temperature and the second
  station reports a valid one
- **THEN** `current` is built from the second station's observation

### Requirement: Response caching and staleness
The proxied payload SHALL be cached in-process with a TTL of `weather_cache_minutes` (default
10), with concurrent requests coalesced so parallel page loads trigger at most one upstream
refresh. On upstream failure, a previously cached payload SHALL be served as-is (its embedded
timestamps marking its age) rather than erroring; with no cached payload the endpoint SHALL
return 502. The forecast and observation fetches SHALL fail independently: if exactly one
succeeds, the response carries that half with the other `null` / empty. In addition to
lazy on-request refresh, a scheduled background job (gated by `weather_enabled`, interval
`weather_cache_minutes`) SHALL proactively refresh the cache so the payload stays current without
client requests, and SHALL broadcast a `weather` update ping on the global live-update bus (see
`live-updates`) when the shaped payload differs from the previously cached one; a failed proactive
refresh SHALL log, keep the stale payload, and broadcast nothing.

#### Scenario: Requests within the TTL hit the cache
- **WHEN** two requests arrive within `weather_cache_minutes` of a successful refresh
- **THEN** the second is served from cache with no upstream calls

#### Scenario: Stale payload served on upstream failure
- **WHEN** the cache TTL has expired, a refresh attempt fails, and a previous payload is cached
- **THEN** the endpoint returns the previous payload successfully

#### Scenario: Cold failure returns 502
- **WHEN** the first request after startup fails to fetch from NWS
- **THEN** the endpoint returns 502 and the next request retries upstream

#### Scenario: Partial upstream failure yields a partial response
- **WHEN** the observation fetch fails but the forecast fetch succeeds
- **THEN** the response carries the forecast periods with `current` null

#### Scenario: Proactive refresh pings on change
- **WHEN** the scheduled weather job refreshes the cache and the shaped payload differs from the
  previous one
- **THEN** a `{topic: "weather", type: "updated"}` message is broadcast on `/api/v1/ws`

#### Scenario: Failed proactive refresh is silent
- **WHEN** the scheduled weather job's upstream refresh fails
- **THEN** the previous payload remains cached and no `weather` ping is broadcast

### Requirement: Pure payload shaping
Transforming NWS payloads (points, forecast, observation) into the endpoint's response shape
SHALL be pure functions of the payloads, testable offline against fixture files with no network.

#### Scenario: Shaping is testable offline
- **WHEN** the shaping functions are given recorded NWS fixture payloads
- **THEN** they produce the documented response shape with no network access

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

### Requirement: Scheduled refresh bypasses the cache TTL
Each tick of the scheduled weather job SHALL fetch upstream regardless of the cached payload's
age. The TTL check SHALL apply only to on-request refreshes. A tick that coincides with a
not-quite-expired cache SHALL still refresh, so the proactive refresh happens every
`weather_cache_minutes`. The forced refresh SHALL otherwise behave like any refresh: it is
coalesced under the same lock as request-driven refreshes, a failure keeps the stale payload, and
last-good AQI carry-forward still applies.

#### Scenario: Every job tick refreshes upstream
- **WHEN** the scheduled job ticks one interval after the previous refresh, while the cached
  payload's age is still marginally under the TTL
- **THEN** the job fetches fresh data from upstream instead of returning the cached payload

#### Scenario: Request path still honors the TTL
- **WHEN** a client requests `/api/v1/weather/current` within the TTL of the last refresh
- **THEN** the cached payload is served with no upstream calls

