# weather Specification

## Purpose

The backend weather feature: current conditions + today's forecast proxied from the National
Weather Service API (`api.weather.gov`) at the shared app-level center coordinate, served at
`/api/v1/weather/current` for the home page's weather strip. Deliberately stateless — no DB
tables, no scheduler job — an in-process TTL cache shields the browser from NWS's two-hop
discovery, User-Agent requirement, and slowness. Not a geo/timeseries source: weather does not
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
(`www.airnowapi.org` current-observations-by-lat/lon endpoint) at the shared center coordinate
settings, gated by the `airnow_api_key` setting (env `AIRNOW_API_KEY`, default empty). With an
empty key the system SHALL make no AirNow requests and `aqi` SHALL be `null`. The AQI fetch
SHALL run within the same cache refresh as the NWS fetches and SHALL fail independently of
them: an AirNow failure (error status, network failure, or no usable observations) SHALL yield
`aqi: null` while leaving the NWS halves untouched, and a successful AQI fetch SHALL NOT rescue
a refresh in which both NWS fetches failed. Shaping the AirNow response SHALL be a pure
function of the payload, testable offline against a fixture: the overall AQI SHALL be the entry
with the maximum `AQI` value across reported pollutants (the EPA convention, identifying the
primary pollutant), entries with missing or negative AQI values SHALL be skipped, and an empty
or all-invalid response SHALL yield `null`.

#### Scenario: AQI disabled by empty key
- **WHEN** `airnow_api_key` is empty and the weather cache refreshes
- **THEN** no request is made to AirNow and the payload carries `aqi: null`

#### Scenario: Overall AQI is the worst pollutant
- **WHEN** AirNow reports O3 at AQI 41 and PM2.5 at AQI 62
- **THEN** `aqi` carries value 62 with PM2.5 as the pollutant and PM2.5's category

#### Scenario: AirNow failure leaves weather intact
- **WHEN** the AirNow request fails during a refresh in which the NWS fetches succeed
- **THEN** the payload carries the NWS conditions and periods with `aqi: null`, and the refresh
  is not treated as an error

#### Scenario: AQI success does not rescue a failed refresh
- **WHEN** both NWS fetches fail during a cold refresh and the AirNow fetch succeeds
- **THEN** the refresh is treated as failed (the endpoint returns 502 with no cached payload)

#### Scenario: AirNow shaping is testable offline
- **WHEN** the AirNow shaping function is given a recorded fixture payload
- **THEN** it produces the documented `aqi` shape with no network access

