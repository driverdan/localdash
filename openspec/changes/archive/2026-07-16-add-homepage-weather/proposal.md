# Add Homepage Weather

## Why

The homepage digest (latest news, upcoming events) has no at-a-glance weather, which is core
local-dashboard content — and the home grid was explicitly built to absorb a weather widget as a
pure addition. Separately, the app's canonical coordinate (`CHATTANOOGA_CENTER`) lives inside the
events feature, so a second feature needing it (weather) would either duplicate it or create a
cross-feature import; it belongs in main config.

## What Changes

- Add a `weather` backend feature: a new `/api/v1/weather/` namespace (router + one
  `include_router` line, per the app-shell convention) exposing `GET /api/v1/weather/current`
  with current conditions and today's forecast periods, proxied from the National Weather
  Service API (`api.weather.gov`) with an in-process TTL cache. No DB tables, no migration, no
  scheduler job — fetch-on-demand with caching.
- Add a full-width weather strip to the homepage, rendered above the news/events widgets. It
  lives inside the existing `home` frontend feature (no new route), with its own independent
  loaded/error state so a weather failure never affects the other widgets.
- Move the shared center coordinate from `app/events/__init__.py` (`CHATTANOOGA_CENTER`) into
  `app/config.py` as settings (`center_lat`/`center_lon`, env-overridable, defaulting to the
  same Chattanooga values). Events (distance origin, CitySpark/Meetup defaults) and weather both
  read it from settings; the events-local constant is removed.
- Not in scope: weather as a geo/timeseries source on the map (the collectors/ingest pipeline is
  untouched); a dedicated `/weather` page; historical weather storage.

## Capabilities

### New Capabilities

- `weather`: the backend weather feature — NWS upstream contract (gridpoint discovery, station
  observations, forecast periods, required User-Agent), the `/api/v1/weather/current` response
  shape, caching/staleness behavior, and error handling.

### Modified Capabilities

- `frontend-home`: the widget grid gains a full-width weather strip above the news and events
  widgets, with the same independent fetch/error isolation the existing widgets have.
- `events`: the distance origin and source defaults (CitySpark radius origin, Meetup search
  center) are now sourced from the shared app-level center setting in main config instead of a
  feature-internal constant — making the center env-configurable where it was previously
  hardcoded.

## Impact

- **Backend**: new `app/weather/` module (NWS client + response shaping + cache) and
  `app/api/weather.py` router; `app/main.py` gains one `include_router` line; `app/config.py`
  gains weather settings (`weather_enabled`, cache TTL) and the shared `center_lat`/`center_lon`.
- **Events refactor**: `app/events/__init__.py` loses `CHATTANOOGA_CENTER`; its importers
  (`app/events/ingest.py`, `app/events/sources/__init__.py`, `app/api/events.py`,
  `tests/test_events_ingest.py`) switch to the settings value. No behavior change at defaults.
- **Frontend**: `frontend/src/features/home/` gains a `WeatherStrip` component plus state/api
  additions; `frontend/src/styles/home.css` gains the strip's full-width grid rules.
- **Dependencies**: none added — the backend already uses httpx; the existing global
  `user_agent` setting satisfies NWS's User-Agent requirement.
- **External services**: adds `api.weather.gov` as an upstream (free, no key, US government);
  current-conditions icons reuse NWS-served icon URLs in the browser, consistent with news story
  images loading from external hosts.
