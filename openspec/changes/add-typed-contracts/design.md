## Context

The review finding holds on `origin/main`, with one correction:

- **No response models.** `grep -rnE "response_model|BaseModel" app` matches only
  `app/collectors/base.py` (`NormalizedObservation`). Handlers build dicts by hand:
  `app/api/timeseries.py` (`entity_detail` 129-139, `entity_track` 171-180, `list_sources`
  238-250, plus the GeoJSON built by `app/geojson.py`), `app/api/events.py` (`_serialize` 28-45,
  `items` 87-91, `tags`), `app/api/news.py` (wraps `app/news/stories.py` 55-67 and 148-160),
  `app/api/root.py` (`/config`), and the weather payload assembled from `app/weather/nws.py`,
  `app/weather/airnow.py` and `WeatherService._refresh`. `/openapi.json` therefore has no
  response schemas.
- **Frontend mirrors.** The brief's count of 39 exported types is high. `frontend/src/features/
  {news,timeseries,events}/types.ts` export 18 names, 26 types are exported across
  `frontend/src/features/`, and the weather and outage shapes live in
  `frontend/src/features/home/api.ts`. The point stands: the frontend keeps hand-written mirrors
  of the JSON.
- **Registry.** `SOURCES` (`app/news/registry.py:39`) is a list of dicts. `use_feed_tags` is an
  optional source key (default `True`) and `kind` an optional feed key (default `"rss"`), read by
  linear scans in `uses_feed_tags` (189) and `feed_kind` (194). `sync_registry` reads the same
  dicts. Tests monkeypatch `registry.SOURCES` with dict lists (`tests/test_news_db.py:21-49`), and
  `tests/test_news_classify.py:56` indexes it by `"slug"`.
- **Refresh results.** `upsert_raw_events` returns `{created, merged, skipped_far}`,
  `retry_failed_geocodes` returns `{retried, resolved}`, and `app/events/refresh.py:38-63` merges
  them with `|=`, adds `reconciled`, and reads six keys back by string. `run_collector`
  (`app/scheduler.py:78`, its `return` at 100) returns `{source, status, error, count}`.
  `news.refresh` returns `{"sources": {label: status}, "clusters": n}`. `Diff` in
  `app/schemas.py` is the only typed result.
- **Stories.** `get_stories` turns SQL rows into dicts with `published` already formatted as an
  ISO string, and `build_stories` turns those into story dicts, sorting by the formatted string.

Wire-format facts that constrain the design (checked against Pydantic 2.14 in the repo's venv):

- Pydantic serialises a UTC `datetime` as `2026-01-01T00:00:00Z`. Handlers today emit
  `.isoformat()`, which gives `+00:00`. Nothing in the frontend breaks on `Z` (every consumer goes
  through `new Date(...)`), but `frontend/src/features/timeseries/state.svelte.ts:102` sorts
  entities by comparing `last_seen_at` strings with `localeCompare`, and Python tests assert
  exact strings (`tests/test_geojson.py:69`, `tests/test_ingest.py:94`,
  `tests/test_news_clustering.py:273`).
- A `float` field turns an integer input into `42.0`. AirNow's `nowcastAQI` and NWS's
  `temperature` and `probabilityOfPrecipitation` arrive as JSON integers and are passed through.
- AirNow's `observed_at` (`app/weather/airnow.py:_observed_at`) is naive when the reporting zone is
  unknown, by design. NWS's `observed_at` is NWS's own string, passed through.
- `/timeseries/observations` returns up to 50,000 features, and `/timeseries/entities` returns
  every active entity. Feature `properties` are `{**raw_jsonb, **our_keys}`.
- FastAPI already runs `jsonable_encoder` over every dict a handler returns, so the GeoJSON routes
  already pay a per-feature encoding cost. Pydantic validation would add a second pass.

## Goals / Non-Goals

**Goals:**

- Every JSON route publishes a named response schema in OpenAPI.
- Handlers build typed objects, so a missing or misspelled field fails in Python (and, once
  `tighten-python-tooling` adds a type checker, at check time) rather than in the browser.
- Refresh results and the news registry are typed records with attribute access.
- Response bodies are unchanged, and tests prove it.

**Non-Goals:**

- Generating the frontend types from OpenAPI. It is the obvious follow-up, but it adds a
  build step and frontend churn this change doesn't need.
- Typing the WebSocket messages. `Diff` is already a dataclass; its features use the same
  entity-properties dict as REST.
- Modelling source-specific GeoJSON properties or the JSONB `latest_properties`/`properties`
  blobs.
- Typing the rows `app/news/fetcher.py` builds for `upsert_articles`. `consolidate-shared-helpers`
  deduplicates that code.
- Changing any response field, status code, or error body.

## Decisions

### 1. Where the models live: a `schemas.py` per feature, plus one shared module

- `app/contracts.py` (new, about 30 lines): `ApiModel`, the base for all response models
  (`ConfigDict(extra="forbid")`, so a handler that passes a field the model lacks fails loudly
  instead of the field being dropped silently), and `IsoDateTime` (decision 2).
- `app/news/schemas.py`, `app/events/schemas.py`, `app/weather/schemas.py`: that feature's
  response models and result dataclasses.
- Timeseries: `app/schemas.py`, beside `Diff`. Its docstring already reads "API response models
  and the ingest Diff structure". If `move-timeseries-into-package` lands first (it is earlier in
  the landing order), this becomes `app/timeseries/schemas.py`.
- GeoJSON envelope models go in `app/geojson.py`, next to the dict helpers that build what they
  describe.
- The app-shell `/config` model (`AppConfig`, two fields) goes in `app/api/root.py`. A separate
  module for two fields isn't worth it.

Alternative: one `app/api/schemas.py` for every feature. Rejected because it breaks the
"feature is a self-contained package" layout `AGENTS.md` describes, and because the refresh
dataclasses are produced by feature code (`app/events/refresh.py`), which should not import from
`app/api/`.

### 2. Datetime rule: keep `.isoformat()` exactly

```python
IsoDateTime = Annotated[datetime, PlainSerializer(lambda d: d.isoformat(), return_type=str)]
```

Every datetime the system produces is declared `IsoDateTime`, and the JSON stays as it is today
(`+00:00` for the UTC values Postgres returns, microseconds only when non-zero, which is Python's
own rule). Weather observation times stay `str | None`: they are an upstream string (NWS) or a
possibly naive local time (AirNow), and parsing them into `datetime` would add a way for the
refactor to change them.

Alternative: accept Pydantic's `Z`. The frontend would parse it, but this would change every
timestamp on the wire. It would also mix two formats in the one string comparison the frontend
does: `live.ts` already sets `new Date().toISOString()` (`Z`) on locally patched entities while
REST serves `+00:00`, and that pre-existing mix is not this change's to fix. Keeping
`.isoformat()` means the refactor changes no timestamp.

### 3. GeoJSON routes: schemas for OpenAPI, no validation

`/timeseries/entities` and `/timeseries/observations` declare
`responses={200: {"model": EntityFeatureCollection}}` (and `ObservationFeatureCollection`) with
`response_model=None`, and keep returning the dicts `app/geojson.py` builds. The documentation
models describe the envelope (`type`, `features[]`, `id`, `geometry` as an open object or `null`)
and the keys the system itself adds to `properties` (`id`, `source`, `external_id`, `category`,
`label`, `last_seen_at`, `active`, `status` for entities; `entity_id`, `source`, `category`,
`status`, `observed_at` for observations), with `extra="allow"` so OpenAPI shows
`additionalProperties`.

Why not validate: 50,000 features × a model per feature is a second pass on top of the
`jsonable_encoder` pass FastAPI already makes, on the heaviest route, for objects that are mostly
open dicts anyway. Validating only the envelope would check almost nothing. If profiling ever
shows `jsonable_encoder` itself is the cost, returning a pre-serialised `ORJSONResponse` is a
separate change.

The other timeseries routes (`/entities/{id}`, `/entities/{id}/track`, `/sources`,
`POST /sources/{key}/refresh`) get full response models. A track is one entity's change history
(observations are written only on change), so its size is modest. `latest_properties` and a track
point's `properties` and `geometry` are `dict[str, Any] | None`.

### 4. Handlers construct models; FastAPI validates on the way out

Routes declare `response_model=` explicitly (or through a return annotation where that reads
better; both appear in OpenAPI), and handlers build model instances, not dicts. The defaults stay:
no `response_model_exclude_none`, so `null` fields are still emitted, and no `by_alias`. Field
order in each model matches today's dict key order, so `curl` output looks the same. Numeric
fields passed through from upstream are typed `int | float`, which Pydantic's smart-mode union
keeps as received. Derived numbers get their exact type (`temperature_f: int`,
`distance_miles: float | None`).

The news `categories` map stays `dict[str, str]`. Pydantic keeps insertion order, which the
frontend relies on for display order.

### 5. Internal results are frozen dataclasses, reused as response models

Refresh results never come from untrusted input, so they need no validation. They are stdlib
`@dataclass(frozen=True, slots=True)`:

- events: `UpsertStats(created, merged, skipped_far)` from `upsert_raw_events`/`run_sources`,
  `GeocodeRetryStats(retried, resolved)` from `retry_failed_geocodes`, and
  `EventsRefreshResult(created, merged, skipped_far, retried, resolved, reconciled)` built in
  `refresh()`. Its `changed_visible_data` property replaces the `any(stats[k] for k in ...)` ping
  check.
- news: `NewsRefreshResult(sources: dict[str, str], clusters: int)`. `fetch_all` keeps returning
  `dict[str, str]` (a label→status map is a mapping, not a record).
- timeseries: `CollectorRun(source, status: Literal["ok", "error"], error, count)`.

FastAPI accepts stdlib dataclasses as `response_model`, so the refresh routes use these directly
and each shape is defined once. Field order matches today's keys, so the JSON doesn't change.

Alternative: `TypedDict`. It would keep `|=` and string-key reads working, but a typo would only
be caught by a type checker the repo does not run yet, and readers would still subscript.
Dataclasses give attribute access and a real constructor.

### 6. News read model: typed rows in, `Story` models out

`get_stories` maps SQL rows to a frozen `StoryArticle` dataclass (`published: datetime`, not a
pre-formatted string). `build_stories` stays pure and returns `list[Story]` (Pydantic, with
`StorySource` links), sorting on `datetime` rather than on ISO strings. The order is the same,
because every value is UTC from the same `timestamptz` column. `get_sources` returns
`list[NewsSourceStatus]`. The route wraps them in `StoriesResponse(categories, stories)` and
`SourcesResponse(sources)`.

### 7. Weather: the parsers return models, and the cache holds a model

`parse_forecast → list[ForecastPeriod]`, `parse_observation → CurrentConditions | None`,
`parse_airnow → AirQuality | None`, and `_refresh → WeatherPayload`. They stay pure, which keeps
the `weather` spec's "Pure payload shaping" requirement satisfied. `_carry_forward_aqi` uses
`payload.model_copy(update={"aqi": prior.aqi})`. `run_weather_refresh`'s `payload !=
_last_weather_payload` comparison works unchanged, because Pydantic models compare by field
values.

### 8. Registry: frozen dataclasses, linear lookups kept

```python
@dataclass(frozen=True, slots=True)
class FeedSpec:
    category: str
    url: str
    kind: Literal["rss", "html"] = "rss"

@dataclass(frozen=True, slots=True)
class Outlet:
    slug: str
    name: str
    homepage: str
    feeds: tuple[FeedSpec, ...]
    enabled: bool = True
    use_feed_tags: bool = True

SOURCES: tuple[Outlet, ...] = (...)
```

`uses_feed_tags(slug)` and `feed_kind(url)` keep their signatures and stay linear scans over
`SOURCES`. With 9 outlets and about 20 feeds, a scan costs nothing, and computing the result per
call keeps `monkeypatch.setattr(registry, "SOURCES", ...)` working in tests. A cached index would
go stale under that patch. `sync_registry` reads attributes. Tests build `Outlet`/`FeedSpec`
instances.

Alternative: Pydantic models for the registry. That adds validation for data that is
code-as-config, checked by tests and by the dataclass constructor's required arguments. A
`Literal` on `kind` together with the type checker from `tighten-python-tooling` covers typos.

### 9. Golden-response tests first

Before any handler changes, phase 0 adds tests that seed known rows (or a fixture weather
payload), call each route through the ASGI client, and compare the parsed JSON to a literal
expected value. These include `null` fields, an integer AQI, `+00:00` timestamps, and a
source-specific GeoJSON property. The refactor must leave these tests untouched. A separate test
asserts that each `/api/v1` JSON route in `/openapi.json` has a `$ref` 200 schema (the spec
scenario).

### 10. Relationship to the sibling changes

Landing order puts this change eighth. It is written against the current tree; the implementer
rebases onto whatever has landed by then.

- `ingest-owns-entity-status` (1): moves the `status` derivation out of the entities handler. No
  conflict: `status` stays a documented property key.
- `add-shared-http-client` (2): touches `WeatherService._make_client` only; this change touches
  the parsers and payload type. Small textual overlap in `service.py`.
- `move-timeseries-into-package` (3): decides where the timeseries models live
  (`app/timeseries/schemas.py`). If it has landed, follow its paths.
- `unify-refresh-orchestration` (4): moves `run_collector` out of `app/scheduler.py` and may give
  each feature a common refresh entry point. **Overlap:** that change reshapes the functions whose
  return types phase 2 here types. If 4 introduces a shared refresh-result shape, phase 2 adopts
  it instead of defining its own. This is the main reason to split phase 2 out (see Open
  Questions).
- `decompose-events-upsert` (5): splits `upsert_raw_events`/`reconcile_events`. **Overlap:** its
  pieces return the counters `UpsertStats` names. Whichever lands second adapts. Landing order puts
  5 first, so this change types the decomposed functions' results.
- `inject-settings-and-clock` (6): passes `now` into `get_stories` and friends. No conflict
  beyond signatures.
- `consolidate-shared-helpers` (7): owns the fetcher's duplicated article-row building. This change
  does not touch it.
- `unify-observation-geometry` (9): changes `NormalizedObservation`, not the response models. No
  conflict.
- `extract-spa-serving` (10): no overlap.
- `tighten-python-tooling` (11): the type checker it adds is what turns these contracts into
  check-time errors. Independent order.
- `remove-dead-schema` (12): may drop `enabled` from `/timeseries/sources`. That change then
  deletes the field from `SourceStatus`, and that removal is its observable change, not this one's.
- `tidy-small-inconsistencies` (13): no overlap.

## Risks / Trade-offs

- [A model field silently changes the wire, for example an int rendered as a float, a `Z`
  timestamp, or a dropped key] → golden-response tests land first and stay unmodified;
  `extra="forbid"` on `ApiModel`; `IsoDateTime` everywhere a datetime is produced; `int | float`
  for passed-through numbers.
- [Validation cost on large responses] → GeoJSON routes are documentation-only. `/events/items`
  (≤ 2,000) and stories (one window) are small enough. The phase 1 verification task records
  before/after latency for `/events/items?limit=2000`.
- [Large diff conflicting with siblings 3–7] → landing order puts this change after them, and the
  phases can merge separately.
- [Documented GeoJSON schema drifts from the dicts actually returned, since it is not validated]
  → the golden test for `/entities` and `/observations` also validates one response against the
  documentation model in-test, so drift fails CI without costing anything at runtime.
- [More code: about 25 small model classes] → each replaces a hand-built dict and a section of
  prose in `AGENTS.md`, and is the prerequisite for generating the frontend types later.

## Migration Plan

Pure refactor plus richer OpenAPI. Deploy as usual (`docker compose up --build`). Rollback is a
revert. No schema migration, no config change.

## Open Questions

- **Split into three changes?** Recommended. Phase 1 (response models) is the bulk and the only
  part with an observable effect (OpenAPI). Phase 2 (typed refresh results) overlaps directly with
  `unify-refresh-orchestration` and `decompose-events-upsert`, and is cleaner written after they
  land. Phase 3 (registry dataclasses) is small and independent. A split would be
  `add-api-response-models`, `type-refresh-results` and `type-news-registry`. The tasks below are
  already grouped that way, so splitting means moving task groups, not rewriting them. This
  proposal stays one change, as the brief asked, until the user decides.
- Generating `frontend/src/features/*/types.ts` from `/openapi.json` (for example with
  `openapi-typescript`) is left as a follow-up proposal.
