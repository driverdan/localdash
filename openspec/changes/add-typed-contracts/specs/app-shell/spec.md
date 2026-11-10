## ADDED Requirements

### Requirement: Declared API response schemas

Every JSON route under `/api/v1` SHALL declare its successful response shape so that the served
OpenAPI document (`/openapi.json`, rendered at `/docs`) contains a named component schema for it.
Declaring a schema SHALL NOT change the response body: field names, the presence of fields whose
value is `null`, and the JSON number type of each value (integer or float) SHALL be the same as
the route's hand-built output before the schema was declared. Datetime values that the API
produces SHALL be ISO-8601 strings with an explicit numeric UTC offset, in the form Python's
`datetime.isoformat()` emits (for example `2026-07-10T10:00:00+00:00`, never a trailing `Z`).
Weather observation times SHALL keep their current form: NWS's are passed through verbatim, and
AirNow's may lack an offset when the reporting time zone is unknown (see the `weather` spec). GeoJSON routes SHALL document the
`FeatureCollection`/`Feature` envelope and the properties the system itself adds, and SHALL leave
each feature's `properties` open to additional, source-specific keys. The live-update WebSocket is
not an HTTP route and is outside this requirement.

#### Scenario: OpenAPI documents a route's response

- **WHEN** a client fetches `/openapi.json`
- **THEN** each JSON `GET` and `POST` route under `/api/v1` (for example
  `GET /api/v1/events/items`, `GET /api/v1/news/stories`, `GET /api/v1/weather/current`,
  `GET /api/v1/timeseries/entities/{entity_id}`) has a `200` response whose content refers to a
  named component schema rather than an untyped object

#### Scenario: Response bodies are unchanged

- **WHEN** a client calls any `/api/v1` JSON route against the same data before and after
  response schemas are declared
- **THEN** the two parsed JSON bodies are equal, including `null`-valued fields and integer
  values that were not rendered as floats

#### Scenario: Datetimes keep a numeric offset

- **WHEN** a client reads a timestamp the system produces, such as a news story's
  `first_published`, an event's `starts_at`, or an entity's `last_seen_at`
- **THEN** it is an ISO-8601 string ending in a numeric offset such as `+00:00`, not `Z`

#### Scenario: Source-specific GeoJSON properties pass through

- **WHEN** a client requests `GET /api/v1/timeseries/entities` and an entity's stored
  properties include a source-specific key that no schema names
- **THEN** that key is present in the feature's `properties` with its stored value
