## 1. AGENTS.md

- [x] 1.1 Routes and features: home at `/`, news at `/news`, all four routes, the router's "four routes" note, the Commands URLs, and the feature list including `home`
- [x] 1.2 Feature-isolation wording: cross-feature imports only through `index.ts`; list the steps for wiring in a new feature
- [x] 1.3 News: content-derived categorization (feed tag, then keyword, then section), `use_feed_tags`, the `kind: html` scrape path, the category recomputed on every fetch, the current clustering algorithm (IDF-weighted similarity, vetoes, 36h window, majority match), migration `0007`, and `/stories` `limit`
- [x] 1.4 Weather: the scheduled `weather_refresh` job and its ping, AirNow (overview, `aqi` in the route description, three upstream calls when configured), and the `airnow_*` config
- [x] 1.5 Scheduler job list (geo collectors, news, events and weather refresh); events overview includes the Chattanooga Zoo; the tables line includes `tags` and `geocode_cache`; the config list includes the `events_*` settings
- [x] 1.6 API conventions: the weather namespace and router; the WebSocket is the global `/api/v1/ws`, not a timeseries route
- [x] 1.7 Geometry: arbitrary geometry with `geom_fingerprint` change detection (no point-only, epsilon or `ST_X` wording)
- [x] 1.8 CI: four jobs with path filtering, the frontend check and Docker build/publish; only the pre-commit lint CI job is still deferred
- [x] 1.9 Dependency pinning: bounded ranges (`~=` or `>=,<`), with a matching fix to the `.github/dependabot.yml` comment
- [x] 1.10 DB-backed test list includes the events tests

## 2. README

- [x] 2.1 News "nine outlets"; events "sorted by start time, filterable by distance"; replace the map "scrub back through" claim with per-entity history in the detail panel

## 3. .env.example

- [x] 3.1 Add a News section (`NEWS_ENABLED`, `NEWS_REFRESH_MINUTES`, `NEWS_STORY_WINDOW_DAYS` with their defaults)
- [x] 3.2 Events: accurate comment (five default sources); add `EVENTS_TRIBE_CALENDARS` and `EVENTS_CITYSPARK_ENABLED` with their shipped defaults
- [x] 3.3 Note that `CENTER_LAT`/`CENTER_LON` also set the weather/AQI location

## 4. API docs

- [x] 4.1 `docs/tdot-smartway-api.md`: rewrite the intro status and the LocalDash mapping section to match `app/collectors/tdot.py` (single `tdot` source, four merged event endpoints, category mapping and `isSevere` override, dedup by id, label/`source_time` fallbacks, 204 handling, cameras/signs excluded)
- [x] 4.2 `docs/hc911-api.md`: point the architecture reference to `AGENTS.md`

## 5. Comments and housekeeping

- [x] 5.1 `app/config.py`: the events "nothing configured by default" comment, the weather "no scheduler" comment, `/api/config` → `/api/v1/config`
- [x] 5.2 `frontend/src/lib/router.svelte.ts` "two routes" comment; `frontend/src/styles/base.css` stylesheet list
- [x] 5.3 Move `.prettierignore` to `frontend/.prettierignore` with paths rewritten relative to `frontend/`; confirm `npm run format` and the pre-commit prettier hook still ignore build output

## 6. Verification

- [x] 6.1 Re-check every edited claim against the code; `pre-commit run --all-files` is clean; `openspec validate sync-docs-and-specs --strict` passes

## 7. Archive phase (hand edits, archive PR only)

- [x] 7.1 After `openspec archive`, hand-edit the `weather` Purpose (drop "no scheduler job") and the `events` Purpose (add the Chattanooga Zoo)
