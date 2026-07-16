# Design — add-homepage-weather

## Context

The homepage (`frontend/src/features/home/`) is a widget grid of digest cards (latest news,
upcoming events) whose CSS was explicitly written so a third widget is "a pure addition, no
restructure". Weather is the natural next digest, decided during exploration as a **full-width
strip above both existing widgets**, sourced from the **National Weather Service API**
(`api.weather.gov`) via a **backend proxy**.

Relevant current state:

- Every feature owns an `/api/v1/<feature>/` namespace as one `APIRouter` module in `app/api/`,
  composed in `app/main.py`. News and events fetch upstream data server-side; nothing in the
  frontend talks to third-party APIs directly.
- The app's canonical coordinate is `CHATTANOOGA_CENTER = (35.0456, -85.3097)` in
  `app/events/__init__.py`, imported by events ingest, the events API, the Meetup/CitySpark
  source config, and events tests. Features must not import from other features, so weather
  cannot reuse it where it lives today.
- `config.py` (pydantic-settings) already carries a global `user_agent` setting; httpx is
  already a dependency. There is no per-request external call anywhere — all upstream access is
  cached or scheduled.

## Goals / Non-Goals

**Goals:**

- Current conditions + today's forecast on the homepage, above the news/events widgets, on every
  viewport size.
- A `weather` backend namespace that follows the existing feature conventions and shields the
  browser from NWS's quirks (two-hop discovery, User-Agent requirement, slowness) behind a cache.
- One shared, env-overridable center coordinate in main config, consumed by both events and
  weather.
- A weather failure degrades the strip only — news/events widgets are unaffected, matching the
  home page's per-widget isolation pattern.

**Non-Goals:**

- Weather on the map / as a timeseries source. AGENTS.md floats weather as a future geo feed;
  this change deliberately does not go through collectors/ingest and does not foreclose that.
- A `/weather` route or full forecast page (multi-day, hourly, radar).
- Storing weather history (no DB tables, no migration).
- A scheduler job — fetch-on-demand with a TTL cache is sufficient for a single-city widget.

## Decisions

### 1. NWS (api.weather.gov) as the upstream

Free, keyless, and authoritative for a US city. Its period forecast is human prose ("Sunny, high
near 92") — literally "today's forecast" with no icon/label vocabulary to invent — and current
conditions are real station observations rather than model output.

*Alternative considered:* Open-Meteo — one call, very reliable, but modeled "current" conditions,
WMO code→label mapping to build and maintain, and a third-party non-commercial dependency where a
government service exists. NWS flakiness is neutralized by the server-side cache instead.

### 2. Backend proxy, not browser-direct fetch

A new `app/api/weather.py` router (mounted at `/api/v1/weather` in `main.py`) backed by an
`app/weather/` module. NWS allows CORS, so browser-direct would work — rejected because it would
be the only feature bypassing the server, would re-fetch on every page load (NWS asks clients to
cache), and NWS's identifying User-Agent expectation belongs server-side (reusing the existing
`user_agent` setting, as the other upstreams do).

### 3. Upstream contract: resolve once, then two cached calls

NWS is two-hop: `GET /points/{lat},{lon}` returns the gridpoint forecast URL and the
observation-stations URL. That metadata is static for a fixed coordinate, so `app/weather/nws.py`
resolves it **once per process** (lazily, on first request; retried on failure rather than cached)
and caches it for the process lifetime. Steady state per cache expiry is then:

```
GET {forecastUrl}                        → today's periods (name, temps °F, prose, precip %)
GET /stations/{first station}/observations/latest → current conditions (temps in °C → convert)
```

*Alternative considered:* hardcoding the Chattanooga gridpoint/station in config — fewer moving
parts but breaks silently if NWS regrids, and defeats the env-configurable center.

### 4. Response shape and staleness

`GET /api/v1/weather/current` returns a single JSON object:

- `current`: temperature (°F), text description, NWS icon URL, wind, humidity, and the
  **observation timestamp** — station obs can lag 20–60 min and must not be presented as live;
  the frontend renders "as of" from this. Station observations with `null` temperature (a known
  NWS quirk) fall back to the next station in the list, else `current` is `null`.
- `periods`: the first two forecast periods verbatim (name, temperature, unit, precip
  probability, short + detailed forecast). **Period names come from NWS** ("Today", "Tonight",
  "This Afternoon") — the widget renders whatever the first periods are named rather than
  hardcoding "Today", because NWS renames the leading period through the day.
- Parsing/shaping NWS payloads into this response is a **pure function**, testable offline
  against fixture payloads (`tests/fixtures/`), matching how the other sources are tested.

Caching: in-process TTL cache (`weather_cache_minutes`, default 10) guarded by an asyncio lock so
concurrent page loads produce one upstream fetch. On upstream failure with a previously good
payload cached, **serve the stale payload** (marked by its timestamps) rather than erroring; with
no cache at all, return 502 and let the strip degrade. Forecast and observation fetches
fail independently — one succeeding still yields a partial response.

### 5. `CHATTANOOGA_CENTER` → settings (`center_lat` / `center_lon`)

Moved to `Settings` in `app/config.py` as two floats defaulting to the current values
(35.0456, -85.3097), env-overridable like everything else in config — consistent with the file's
"nothing deployment-specific is hardcoded" ethos, and it is what "shared throughout the app"
means here. A `center` property returns the `(lat, lon)` tuple so call sites keep tuple
ergonomics. `app/events/__init__.py` drops the constant; `app/events/ingest.py`,
`app/events/sources/__init__.py`, `app/api/events.py`, and `tests/test_events_ingest.py` switch
to `get_settings().center`. Behavior at defaults is identical; `MEETUP_RADIUS_MILES` stays where
it is (deliberately not config, per its comment).

*Alternative considered:* a module-level constant in `config.py` — shares the value but keeps it
hardcoded; settings cost the same and make the center deployable elsewhere.

### 6. Frontend: strip inside the `home` feature, no new frontend feature

There is no `/weather` route, so no `features/weather/` namespace: a `WeatherStrip.svelte`
component under `features/home/components/`, a `loadWeather()` in `home/api.ts`, and
`weather`/`weatherLoaded`/`weatherError` state in `home/state.svelte.ts` — exactly the pattern
the two existing widgets use, fired in parallel from `HomePage.svelte`'s `onMount`. If the API
errors, the strip collapses to a one-line notice (no layout hole), and news/events render
normally.

Layout: the strip is the grid's first child with `grid-column: 1 / -1` in
`frontend/src/styles/home.css` — above both widgets at every width, columns untouched. Styling
follows the global styling contract (plain global CSS, theme variables, no scoped styles).
Current-conditions icon is the NWS-served icon URL in an `<img>`, consistent with story-card
images loading from external hosts.

### 7. Config additions

```
center_lat: float = 35.0456        # shared app-level center (weather, events origin)
center_lon: float = -85.3097
weather_enabled: bool = True       # gates router registration like news/events
weather_cache_minutes: int = 10    # TTL for the proxied NWS payload
```

## Risks / Trade-offs

- **NWS slowness/outages** → TTL cache + serve-stale-on-error; the strip shows a notice (or
  stale data with its "as of" time) and never blocks the other widgets.
- **Stale station observations presented as fresh** → observation timestamp is part of the
  response contract and rendered as "as of HH:MM".
- **NWS regrids or renames endpoints** (rare) → gridpoint discovery is per-process, not
  hardcoded; a restart re-resolves. Failures of discovery itself are retried on the next request.
- **First homepage hit after startup pays the full three-call chain** (~1–2 s worst case) → the
  strip has its own loading state; news/events load in parallel and are not delayed. Accepted
  over a scheduler prefetch job to keep the feature stateless.
- **In-process cache means one fetch per uvicorn worker** → the deployment is single-process;
  acceptable.
- **External icon URLs** (browser loads images from NWS) → consistent with existing story-card
  images; offline dashboards lose the icon but keep text/temps.
