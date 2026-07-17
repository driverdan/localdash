## 1. AQI shape gains an observation timestamp

- [ ] 1.1 In `app/weather/airnow.py`, extend `parse_airnow` to derive `observed_at` (ISO-8601) on the winning entry from AirNow's `DateObserved`, `HourObserved`, and `LocalTimeZone`, with a small lookup mapping the standard US zone abbreviations AirNow emits to fixed UTC offsets; emit a display-only naive timestamp when the abbreviation is unknown, and add `observed_at` to the returned dict.
- [ ] 1.2 Add an AirNow fixture (or extend the existing `current` fixture) carrying `DateObserved`/`HourObserved`/`LocalTimeZone` on the winning entry.
- [ ] 1.3 In `tests/test_weather.py`, assert `parse_airnow` produces the expected `observed_at`, and that existing shape assertions still hold.

## 2. Config: max carry-forward age

- [ ] 2.1 Add `airnow_stale_minutes: int = 120` (env `AIRNOW_STALE_MINUTES`) to `app/config.py`, beside `weather_cache_minutes`.
- [ ] 2.2 Document `AIRNOW_STALE_MINUTES` in `.env.example`.

## 3. Service: carry forward last-good AQI

- [ ] 3.1 In `app/weather/service.py`, after `_refresh` returns, when the fresh payload's `aqi` is `None` and the retained `self._payload` has a non-`None` `aqi` whose `observed_at` is within `airnow_stale_minutes` of now, copy that prior `aqi` into the fresh payload before storing it.
- [ ] 3.2 Compute the age from `observed_at`; when the offset was unresolvable (naive display-only timestamp), fall back to the fetch-time bound so an unparseable reading still ages out.
- [ ] 3.3 Keep this in the shared `get_current`/`_refresh` path so scheduled and on-demand refreshes both inherit it; confirm a carried-forward AQI leaves the shaped payload equal so no spurious `weather` ping is broadcast.

## 4. Service tests

- [ ] 4.1 Add a test: a prior refresh yields an AQI, a later refresh's AirNow fetch fails while NWS succeeds → payload carries the prior AQI with its `observed_at` unchanged.
- [ ] 4.2 Add a test: prior AQI older than `airnow_stale_minutes` and current AirNow fetch fails → payload carries `aqi: null`.
- [ ] 4.3 Add a test: AirNow fails with no prior AQI ever cached → `aqi: null`, refresh not treated as an error (adjust the existing `test_airnow_failure_leaves_weather_intact` if it now needs a no-prior precondition).
- [ ] 4.4 Confirm `test_airnow_success_does_not_rescue_cold_failure` and the cold-failure behavior still pass unchanged.

## 5. Frontend

- [ ] 5.1 In `frontend/src/features/home/api.ts`, add `observed_at: string | null` to the `Aqi` type.
- [ ] 5.2 In `frontend/src/features/home/components/WeatherStrip.svelte`, optionally render the AQI "as of" time on the chip using the existing `fmtAsOf` helper.

## 6. Specs and verification

- [ ] 6.1 Run backend tests (`pytest tests/test_weather.py`) and `svelte-check` / frontend build; rebuild via `docker compose up --build`.
- [ ] 6.2 Verify end-to-end that a simulated AirNow failure keeps the last-good AQI on the strip with an "as of" time, and that it drops to blank past the max age.
