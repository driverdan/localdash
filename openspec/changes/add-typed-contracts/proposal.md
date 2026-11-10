## Why

Most data in the backend crosses boundaries as hand-built dicts. No route declares a response
model (`grep -rnE "response_model|BaseModel" app` finds only `NormalizedObservation`), so
`/openapi.json` and `/docs` describe every response as an untyped object. A misspelled or dropped
key surfaces only in the frontend, which keeps its own copies of the shapes in
`frontend/src/features/*/types.ts` and `frontend/src/features/home/api.ts`. Inside the backend, the
news registry is a list of dicts with optional keys found by linear scans, and refresh results are
dicts merged with `|=` and read back by string key. Typed contracts make these shapes explicit,
checked at the boundary, and visible to the tooling that `tighten-python-tooling` adds.

## What Changes

- **API response models.** Every JSON route under `/api/v1` gets a Pydantic response model,
  declared with `response_model=` (or the return annotation). Each model lives in a schemas
  module beside the code that produces it: `app/news/schemas.py`, `app/events/schemas.py`,
  `app/weather/schemas.py`, and `app/timeseries_schemas.py` for the timeseries routes, whose
  code sits at the top level of `app/`. This is a layout preference, not a boundary rule. A small
  shared module, `app/contracts.py`, holds the base model and the datetime type that keeps
  today's wire format.
- **GeoJSON routes are documented, not validated.** `/timeseries/entities` and
  `/timeseries/observations` (up to 50,000 features) declare their schema for OpenAPI only. Their
  per-feature `properties` stay open objects, because they carry arbitrary source fields passed
  through from JSONB.
- **Typed internal results.** The events refresh statistics, the news refresh result and the
  timeseries collector run result become frozen dataclasses instead of dicts. The two routes
  that return them (`POST /events/refresh`, `POST /news/refresh`) and
  `POST /timeseries/sources/{key}/refresh` use those dataclasses as their response models.
- **Typed news read model.** `app/news/stories.py` builds stories from typed article rows and
  returns `Story` models, instead of converting rows to dicts and then to other dicts.
- **Typed weather payload.** The NWS/AirNow shaping functions return models, and the weather
  service caches a `WeatherPayload` instead of a dict.
- **Dataclass news registry.** `SOURCES` in `app/news/registry.py` becomes a tuple of frozen
  `Outlet` dataclasses holding frozen `FeedSpec`s, with `use_feed_tags` and `kind` as fields that
  have defaults, instead of optional dict keys.
- **Wire JSON does not change.** Field names, `null` handling, integer/float rendering and
  datetime strings stay as they are, and models declare fields in today's key order. Datetimes keep Python's
  `.isoformat()` form (`+00:00`, not Pydantic's default `Z`). Golden-response tests pin this
  before the refactor starts.
- **Observable change:** `/openapi.json` and the `/docs` page gain component schemas and typed
  200 responses for every JSON route. No endpoint's response body changes.

Out of scope: generating the frontend TypeScript types from the OpenAPI document (a natural
follow-up once the schemas exist); the WebSocket diff messages (`Diff` is already typed, and its
features share the entity-properties contract); the article rows `app/news/fetcher.py` builds for
upsert (deduplicated by `consolidate-shared-helpers`).

This is the largest of the parallel refactors. It is written as one change in three phases
(response models, typed internal results, registry dataclasses) that can each merge on their own.
`design.md` recommends splitting it into three changes along those lines; see Open Questions.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `app-shell`: adds a requirement that every JSON route under `/api/v1` publishes its response
  schema in the OpenAPI document, keeps datetimes in offset-bearing ISO-8601 form, and leaves
  GeoJSON feature properties open. Feature specs (`timeseries`, `news`, `events`, `weather`) keep
  their requirements unchanged: their response shapes and refresh results are the same as before.

## Impact

- New: `app/contracts.py`, `app/timeseries_schemas.py`, `app/news/schemas.py`,
  `app/events/schemas.py`, `app/weather/schemas.py`.
- Changed: `app/geojson.py` (OpenAPI-only GeoJSON models beside the existing
  dict helpers), `app/api/{timeseries,news,events,weather,root}.py`, `app/news/{stories,registry,
  refresh,fetcher,classify}.py` (registry attribute access; `fetch_all` result), `app/events/
  {ingest,refresh}.py`, `app/weather/{nws,airnow,service}.py`, `app/scheduler.py`
  (`run_collector` result; weather payload comparison).
- Tests: new golden-response tests per endpoint. Updated `tests/test_news_db.py` (registry
  monkeypatch builds `Outlet`s), `tests/test_news_classify.py`, `tests/test_news_clustering.py`
  (`build_stories` rows), `tests/test_weather.py` (model attributes), `tests/test_events_ingest.py`,
  `tests/test_events_cityspark.py`, `tests/test_api_events.py`, `tests/test_live_signals.py`
  (stats and run results by attribute).
- `AGENTS.md`: where response models live, the datetime rule, the GeoJSON exception, and the
  registry's dataclass form.
- No new dependencies (Pydantic 2 already ships with FastAPI). No migration. No frontend change.
