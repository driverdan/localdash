Phases 0–1 are the response-model work, phase 2 the typed refresh results, and phase 3 the news
registry. Each phase leaves the suite green and can merge on its own; if the change is split (see
design.md Open Questions), phases 0–1, 2 and 3 become the three changes. Paths are those on
`origin/main`. If `extract-orm-base` has landed, `Diff` is in `app/diff.py` rather than
`app/schemas.py`. This change adds nothing to either file. If `unify-refresh-orchestration` has
landed, read
`app/scheduler.py:run_collector` as its new home.

## 0. Pin the wire format (before touching any handler)

- [x] 0.1 Add `tests/test_api_contracts.py` with golden-response tests that seed known rows and compare parsed JSON to literal expected values for: `GET /timeseries/entities` (including a source-specific key in stored `latest_properties` and an inactive entity's `"Closed"` status), `/timeseries/entities/{id}`, `/timeseries/entities/{id}/track` (one point and one polygon observation, so `lon`/`lat` are `null` for the polygon), `/timeseries/observations`, `/timeseries/sources`, `GET /news/stories`, `/news/sources`, `GET /events/items`, `/events/tags`, `GET /config`
- [x] 0.2 Add golden tests for `GET /weather/current` from the existing NWS/AirNow fixtures through the service's mock transport, covering an integer AQI `value`, a `null` `wind_mph`, and the verbatim NWS `observed_at`
- [x] 0.3 Add golden tests for the three refresh routes (`POST /events/refresh`, `POST /news/refresh`, `POST /timeseries/sources/{key}/refresh` with a fake collector), asserting the exact key set and value types
- [x] 0.4 Make every expected timestamp in these tests a literal `+00:00` string, and every expected integer a literal int, so a `Z` or `42.0` regression fails

## 1. Response models (phases 1a–1f; one commit each)

- [ ] 1.1 Add `app/contracts.py` with `ApiModel` (`ConfigDict(extra="forbid")`) and `IsoDateTime` (`Annotated[datetime, PlainSerializer(lambda d: d.isoformat(), return_type=str)]`), with a module docstring stating the datetime rule and why
- [ ] 1.2 Add `tests/test_contracts.py`: `IsoDateTime` emits `+00:00` for UTC, keeps non-UTC offsets, and keeps microseconds only when non-zero; `ApiModel` rejects unknown fields
- [ ] 1.3 (1a, app shell) Add `AppConfig` in `app/api/root.py` and declare it on `/config`
- [ ] 1.4 (1b, events) Add `app/events/schemas.py` with `EventLink`, `EventItem`, `Origin`, `EventsResponse` and `TagsResponse`, fields in today's key order. Replace `_serialize` with an `EventItem` constructor, set `response_model=` on `/items` and `/tags`, and drop the `-> dict` annotations
- [ ] 1.5 (1c, news) Add `app/news/schemas.py` with `StorySource`, `Story`, `StoriesResponse`, `NewsSourceStatus` and `SourcesResponse`. Add the frozen `StoryArticle` row dataclass. Rewrite `build_stories` to take `list[StoryArticle]` and return `list[Story]`, sorting on `datetime`. `get_stories` and `get_sources` return models. Set `response_model=` on `/stories` and `/sources`
- [ ] 1.6 (1c) Update `tests/test_news_clustering.py` (`_row` builds `StoryArticle` with `datetime` published; assertions read attributes or `model_dump(mode="json")`) and `tests/test_news_db.py` story/source assertions
- [ ] 1.7 (1d, weather) Add `app/weather/schemas.py` with `CurrentConditions`, `ForecastPeriod`, `AirQuality` and `WeatherPayload`. Passed-through numbers (`temperature`, `precip_percent`, AQI `value`) are `int | float`; `observed_at` fields are `str | None`. Make `parse_forecast`, `parse_observation` and `parse_airnow` return models, have `WeatherService` cache a `WeatherPayload` (`_carry_forward_aqi` via `model_copy`), and set `response_model=WeatherPayload` on `/current`
- [ ] 1.8 (1d) Update `tests/test_weather.py` for model attributes, and confirm `tests/test_live_signals.py`'s weather ping tests still pass with model equality in `run_weather_refresh`
- [ ] 1.9 (1e, timeseries) Add `app/timeseries_schemas.py` with `EntitySnapshot`, `TrackPoint` and `SourceStatus` (keep `enabled` for now; `remove-dead-schema` owns removing it). Set response models on `/entities/{id}`, `/entities/{id}/track` and `/sources`
- [ ] 1.10 (1f, GeoJSON) In `app/geojson.py` add documentation-only models: `EntityProperties` and `ObservationProperties` (`extra="allow"`, system keys only), plus `EntityFeature`/`EntityFeatureCollection` and `ObservationFeature`/`ObservationFeatureCollection`. Declare them on `/entities` and `/observations` via `responses={200: {"model": ...}}` with `response_model=None`, and leave the returned dicts as they are
- [ ] 1.11 (1f) In `tests/test_api_contracts.py`, validate one `/entities` and one `/observations` response against the documentation models, so the docs cannot drift from the dicts
- [ ] 1.12 Add an OpenAPI test: every `/api/v1` JSON route in `app.openapi()` (the WebSocket excluded) has a 200 response whose schema is a `$ref` to a named component
- [ ] 1.13 Check that the golden tests from phase 0 pass unmodified
- [ ] 1.14 Record before/after latency for `GET /events/items?limit=2000` and `GET /news/stories` on a dev database, and note the numbers in the implementation PR

## 2. Typed refresh results

- [ ] 2.1 In `app/events/schemas.py` add frozen dataclasses `UpsertStats`, `GeocodeRetryStats` and `EventsRefreshResult`, the last with a `changed_visible_data` property. Return them from `upsert_raw_events`/`run_sources` (or the functions `decompose-events-upsert` split them into) and from `retry_failed_geocodes`. Build `EventsRefreshResult` in `app/events/refresh.py` and drop `|=` and the string-key reads
- [ ] 2.2 Set `response_model=EventsRefreshResult` on `POST /events/refresh`
- [ ] 2.3 In `app/news/schemas.py` add `NewsRefreshResult(sources: dict[str, str], clusters: int)`, return it from `app/news/refresh.py:refresh`, and declare it on `POST /news/refresh`. Annotate `fetch_all` as `-> dict[str, str]`
- [ ] 2.4 In `app/timeseries_schemas.py` add `CollectorRun(source, status: Literal["ok", "error"], error, count)`, return it from `run_collector`, and declare it on `POST /timeseries/sources/{key}/refresh`
- [ ] 2.5 If `unify-refresh-orchestration` introduced a shared refresh-result type, use it instead of 2.1–2.4's per-feature names, keeping the JSON fields
- [ ] 2.6 Update `tests/test_events_ingest.py`, `tests/test_events_cityspark.py`, `tests/test_api_events.py` and `tests/test_live_signals.py` from `stats["x"]`/`result["x"]` to attribute access, and confirm the refresh golden tests from 0.3 pass unmodified

## 3. News registry dataclasses

- [ ] 3.1 In `app/news/registry.py` add frozen `FeedSpec(category, url, kind: Literal["rss", "html"] = "rss")` and `Outlet(slug, name, homepage, feeds: tuple[FeedSpec, ...], enabled=True, use_feed_tags=True)`, and rewrite `SOURCES` as `tuple[Outlet, ...]`, keeping every comment beside its outlet
- [ ] 3.2 Rewrite `uses_feed_tags`, `feed_kind` and `sync_registry` to use attributes. Keep both lookups as linear scans over `SOURCES`, so monkeypatching still works; add a comment saying so
- [ ] 3.3 Update the `use_feed_tags: False` wording in `app/news/classify.py` and `app/news/fetcher.py` comments to the attribute form
- [ ] 3.4 Update `tests/test_news_db.py` (`TEST_SOURCES_V1/V2` and `TEST_SOURCE_GONE` built from `Outlet`/`FeedSpec`) and `tests/test_news_classify.py:56` (`s.slug`)
- [ ] 3.5 Add a registry test: every outlet slug and feed URL is unique, and every feed category is a key of `CATEGORIES`

## 4. Documentation

- [ ] 4.1 `AGENTS.md` "API / frontend conventions": response models live in a schemas module beside the code that produces them (`app/<pkg>/schemas.py`, `app/timeseries_schemas.py` for the top-level timeseries code), as a layout preference consistent with the guideline from `relax-backend-feature-separation`; the shared `app/contracts.py`; the `IsoDateTime` rule (never emit `Z`); GeoJSON routes are documented, not validated, and their properties stay open; new routes must declare a response model; `/docs` now shows schemas; generating frontend types is a possible follow-up
- [ ] 4.2 `AGENTS.md` news section: the registry is a tuple of frozen `Outlet`/`FeedSpec` dataclasses (`kind`, `use_feed_tags` as defaulted fields)
- [ ] 4.3 `AGENTS.md` weather section: the shaping functions return models and the service caches a `WeatherPayload`

## 5. Verification

- [ ] 5.1 Full `pytest` passes against the temporary test database, and the phase 0 golden tests are byte-identical to when they were added (`git diff` on them is empty)
- [ ] 5.2 `grep -rnE "response_model|responses=" app/api` covers every route decorator in `app/api/`
- [ ] 5.3 `docker compose up --build`, open `/docs`, and confirm the schemas render; spot-check `/map`, `/news`, `/events` and the home page in the browser
- [ ] 5.4 `ruff` and the pre-commit hooks pass; `npm run check` in `frontend/` is unaffected (no frontend changes)
