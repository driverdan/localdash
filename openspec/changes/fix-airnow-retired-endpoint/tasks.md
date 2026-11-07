## 1. Fixtures

- [ ] 1.1 Replace `tests/fixtures/airnow/current.json` with a new-format payload based on
      the recorded Chattanooga response (camelCase keys, `hourObserved` "22:00",
      `localTimeZone` "EST"). Include two entries, `OZONE` at `nowcastAQI` 41 ("Good") and
      `PM2.5` at 62 ("Moderate"), so the worst-pollutant test keeps its values.
- [ ] 1.2 Add `tests/fixtures/airnow/no_observations.json` with the recorded 200
      `WebServiceError` "no observations ... within 50 miles" envelope.

## 2. Shaping (`app/weather/airnow.py`)

- [ ] 2.1 Add a pure `aqi_category(value)` helper that maps an AQI value to an EPA
      category 1–6 using the upper bounds 50/100/150/200/300.
- [ ] 2.2 Rewrite `parse_airnow` for the new fields:
      - return `None` for a non-list payload;
      - pick the max numeric, non-negative `nowcastAQI`;
      - pass `parameterName` and `aqiCategoryName` through verbatim;
      - set `category` with `aqi_category`.
- [ ] 2.3 Update `_observed_at` to read `dateObserved`/`hourObserved`/`localTimeZone`.
      Parse the hour from an `"HH:MM"` string (also accept an int); keep the timezone
      table and the naive fallback.
- [ ] 2.4 Add a pure `airnow_error_messages(payload)` helper that returns the `Message`
      strings of a `WebServiceError` envelope, or `[]` for anything else.
- [ ] 2.5 Update the module and function docstrings and comments to describe the new
      endpoint's payload.

## 3. Fetch (`app/weather/service.py`)

- [ ] 3.1 Set `AIRNOW_URL` to `https://www.airnowapi.org/aq/observation/current/ziplatlong/`.
      Drop the `distance` param and `AIRNOW_DISTANCE_MILES`.
- [ ] 3.2 In `_fetch_aqi`, on a non-2xx status, best-effort decode the body and log one
      warning that includes the status and `airnow_error_messages`, then return `None`.
      Keep `exc_info` logging for network and decode errors.
- [ ] 3.3 In `_fetch_aqi`, on a 200 envelope, log one warning with the messages and return
      `None`. Otherwise return `parse_airnow(...)`.

## 4. Tests (`tests/test_weather.py`)

- [ ] 4.1 Update the parse tests (worst pollutant, unknown timezone, sentinel skip, no
      usable entries) for the new field names and the expected
      `observed_at` "2026-11-06T22:00:00-05:00".
- [ ] 4.2 Add an `aqi_category` breakpoint test (50/51/150/151/300/301 → 1–6) and a test
      that `parse_airnow` returns `None` for the envelope fixture.
- [ ] 4.3 Add a service test asserting the request goes to the new endpoint with
      `latitude`/`longitude`/`API_KEY` and no `distance`.
- [ ] 4.4 Add a service test: a 200 `no_observations` envelope yields `aqi: null` (and
      carries forward a fresh prior AQI), is not a refresh error, and logs AirNow's message.
- [ ] 4.5 Adapt `test_airnow_failure_log_does_not_leak_key`: the 410 response carries the
      retired-service envelope. Assert the warning includes the status and that message,
      and that the key is absent and redacted. Keep the 500 case (no body) working.
- [ ] 4.6 Run `pytest` plus the project's lint and type checks; all pass.

## 5. Verify live

- [ ] 5.1 Rebuild with `sg docker -c 'docker compose up --build -d'`. Confirm the app log
      shows a 200 from `/aq/observation/current/ziplatlong/` and that `GET /api/v1/weather`
      returns a non-null `aqi` with a category number and name.
