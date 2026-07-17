# weather Specification (delta)

## ADDED Requirements

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
  never synthesized, because NWS renames the leading period through the day.

#### Scenario: Fetching current weather
- **WHEN** a client requests `GET /api/v1/weather/current` and NWS is reachable
- **THEN** it receives `current` conditions with an observation timestamp and the first two
  forecast periods with their NWS period names

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
upstream calls: the gridpoint forecast, and the latest observation from the discovered station
list. All NWS requests SHALL send the application's configured `user_agent`. Observation
temperatures (reported by NWS in °C) SHALL be converted to °F; an observation with a null
temperature SHALL fall back to the next station in the discovered list, and `current` SHALL be
`null` if no station yields a usable observation.

#### Scenario: Discovery is resolved once per process
- **WHEN** multiple cache-expired requests are served over the life of one process
- **THEN** `GET /points/{lat},{lon}` is called at most once (on first use), and subsequent
  refreshes call only the forecast and observation endpoints

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
succeeds, the response carries that half with the other `null` / empty.

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

### Requirement: Pure payload shaping
Transforming NWS payloads (points, forecast, observation) into the endpoint's response shape
SHALL be pure functions of the payloads, testable offline against fixture files with no network.

#### Scenario: Shaping is testable offline
- **WHEN** the shaping functions are given recorded NWS fixture payloads
- **THEN** they produce the documented response shape with no network access
