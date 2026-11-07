## Why

The homepage AQI chip has been blank since October 1, 2026. AirNow retired the endpoint
the weather service calls (`/aq/observation/latLong/current/`). Every request now returns
HTTP 410 with `"This web service has been retired as of October 1, 2026"`. The failure is
graceful by design (`aqi: null`, NWS halves unaffected), so the only signal was a
generic `HTTPStatusError` warning in the logs every 10 minutes. AirNow's June 2026 notice
names `/aq/observation/current/ziplatlong/` as the replacement. It accepts the existing
API key, but its response has a different shape, so changing the URL alone is not enough.

## What Changes

- Point the AQI fetch at AirNow's replacement endpoint,
  `/aq/observation/current/ziplatlong/`, still keyed by the shared center coordinate. Drop
  the `distance` parameter, which the new service ignores (it always applies a fixed
  50-mile "closest reading by pollutant" lookup).
- Rewrite the AirNow shaping function for the new payload:
  - lowerCamelCase keys;
  - `nowcastAQI` in place of `AQI`;
  - `hourObserved` as an `"HH:MM"` string;
  - `aqiCategoryName` with no category number;
  - `OZONE` in place of `O3`.
- Derive the EPA category number (1–6) from the AQI value using the standard EPA
  breakpoints. The new payload no longer carries it, and the frontend chip's colors key
  off it. The weather API's `aqi` shape is unchanged.
- Treat AirNow's `{"WebServiceError": [...]}` envelope (returned with HTTP 200 when no
  monitor has data, and with 4xx/410 on errors) as "no usable AQI". Last-good carry-forward
  still applies.
- Include AirNow's error message text in the logged warning, so a future retirement or
  key problem reads as such in the logs instead of a bare status code. The API key stays
  redacted.
- Replace the AirNow test fixture with one recorded from the new endpoint, and add a
  fixture for the no-observations envelope.

No **BREAKING** changes: the `/api/v1/weather` response contract and the frontend are
untouched.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `weather`: The "AirNow AQI upstream contract" requirement changes:
  - the endpoint it names;
  - the payload fields the shaping reads (`nowcastAQI`, `aqiCategoryName`,
    `dateObserved`/`hourObserved`/`localTimeZone`);
  - the category number is now derived from the AQI value;
  - AirNow's error envelope counts as no usable observations;
  - AirNow's error messages must appear in the failure log.

## Impact

- `app/weather/service.py`: `AIRNOW_URL`, request params (drop `distance` and
  `AIRNOW_DISTANCE_MILES`), error-envelope handling and logging in `_fetch_aqi`.
- `app/weather/airnow.py`: `parse_airnow` and `_observed_at` for the new field names
  and hour format; new EPA category-from-value helper; error-message extraction helper.
- `tests/fixtures/airnow/`: new-format `current.json`; new `no_observations.json`.
- `tests/test_weather.py`: AirNow parse and service tests updated for the new
  shape. Add tests for the envelope and derived categories.
- No config, schema, frontend, or dependency changes. Existing `AIRNOW_API_KEY` values
  keep working.
