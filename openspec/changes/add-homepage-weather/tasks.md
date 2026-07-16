## 1. Shared center configuration

- [x] 1.1 Add `center_lat` / `center_lon` settings (defaults 35.0456 / -85.3097) and a `center`
      tuple property to `Settings` in `app/config.py`
- [x] 1.2 Remove `CHATTANOOGA_CENTER` from `app/events/__init__.py` and switch its importers
      (`app/events/ingest.py`, `app/events/sources/__init__.py`, `app/api/events.py`) to
      `get_settings().center`; keep `MEETUP_RADIUS_MILES` where it is
- [x] 1.3 Update `tests/test_events_ingest.py` (and any other test referencing the constant) to
      the settings value; add a config test covering the new settings/property in
      `tests/test_config.py`; run `pytest` to confirm no events regressions

## 2. Weather backend

- [x] 2.1 Add `weather_enabled` and `weather_cache_minutes` settings to `app/config.py`
- [x] 2.2 Create `app/weather/nws.py`: pure shaping functions (points payload → forecast/stations
      URLs; forecast payload → first two periods; observation payload → current conditions with
      °C→°F conversion and null-temperature detection)
- [x] 2.3 Create the fetch/cache layer in `app/weather/` : lazy per-process gridpoint discovery
      (failures not cached), two-call steady-state refresh with independent forecast/observation
      failure handling and station fallback, TTL cache with asyncio-lock request coalescing,
      serve-stale-on-error, `user_agent` header on all NWS requests
- [x] 2.4 Create `app/api/weather.py` router (`GET /current`, 502 on cold failure) and register
      it in `app/main.py` under `/api/v1/weather` gated by `weather_enabled`
- [x] 2.5 Record NWS fixture payloads under `tests/fixtures/` and add offline tests for the
      shaping functions (period passthrough, °C→°F, null-temp fallback) and cache behavior
      (TTL hit, stale-on-error, cold 502, partial response); run `pytest`

## 3. Frontend weather strip

- [x] 3.1 Add weather types + `loadWeather()` to `frontend/src/features/home/api.ts` and
      `weather` / `weatherLoaded` / `weatherError` state to `home/state.svelte.ts`
- [x] 3.2 Create `WeatherStrip.svelte` under `features/home/components/`: current conditions
      (temp, description, icon, "as of" time), NWS-named forecast periods, loading state, and a
      one-line error notice; render it from `HomePage.svelte` with the fetch fired in `onMount`
      alongside the existing two
- [x] 3.3 Add `.weather-strip` rules to `frontend/src/styles/home.css` (first grid child,
      `grid-column: 1 / -1`, theme variables, no scoped styles)
- [x] 3.4 Run `npm run check` and `npm run build`; verify the strip on `/` (wide + narrow
      viewport) against a running backend, including the error notice with the backend stopped

## 4. Docs & verification

- [x] 4.1 Update `AGENTS.md`: weather feature summary (namespace, no-DB/no-scheduler design,
      NWS gotchas), new config settings, and the shared center note in the events section
- [x] 4.2 Full pass: `pytest`, `npm run check`, `npm run build`, and
      `docker compose up --build` smoke test of `/` and `/api/v1/weather/current`
