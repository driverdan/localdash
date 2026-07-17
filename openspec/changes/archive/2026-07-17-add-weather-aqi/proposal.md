## Why

The home page weather widget shows conditions and forecast but no air quality, which is a
routine go-outside/stay-inside signal (pollen-season ozone days, wildfire smoke PM2.5). AirNow
publishes hourly AQI observations for the Chattanooga area behind a free API key, which is
already in `.env` as `AIRNOW_API_KEY`.

## What Changes

- The weather service fetches current AQI observations from the AirNow API at the shared center
  coordinate and folds a shaped `aqi` object into the cached `/api/v1/weather/current` payload as
  a third independently-failing half (alongside `current` and `periods`).
- The `aqi` object carries the overall AQI value (max across reported pollutants, per EPA
  convention), the EPA category number and name, and the primary pollutant name; it is `null`
  when AirNow is unconfigured, unreachable, or reports no observations.
- New `airnow_api_key` setting (env `AIRNOW_API_KEY`), defaulting to empty; an empty key
  disables the AirNow fetch entirely (no upstream call, `aqi: null`), mirroring the
  `events_meetup_token` empty-disables pattern.
- The home page weather widget renders the AQI as a color-coded EPA category chip in the
  current-conditions area when `aqi` is present, and renders nothing AQI-related when it is
  `null`.
- AirNow payload shaping is a pure, fixture-testable function like the existing NWS parsers.

## Capabilities

### New Capabilities

None — AQI extends the existing weather and home capabilities.

### Modified Capabilities

- `weather`: the current-conditions endpoint payload gains an `aqi` half; the upstream contract
  gains the AirNow source (key-gated, independently failing, one extra steady-state call — the
  "exactly two upstream calls" requirement changes); pure-shaping requirement covers the AirNow
  parser.
- `frontend-home`: the weather widget requirement gains the AQI category chip (rendered only
  when the payload carries `aqi`).

## Impact

- Backend: `app/config.py` (new setting), `app/weather/service.py` (AirNow fetch joined to the
  refresh), new `app/weather/airnow.py` parser, `tests/test_weather.py` + AirNow fixture.
- Frontend: `frontend/src/features/home/api.ts` (payload type), `WeatherStrip.svelte` (chip
  markup + EPA category colors).
- Upstream: adds `www.airnowapi.org` as a runtime dependency; at the default 10-minute cache TTL
  the app makes ~6 AirNow requests/hour against the key's 500/hour limit.
- No DB, migrations, scheduler, or live-updates changes: AQI rides the existing cache, proactive
  refresh job, and `weather` ping.
