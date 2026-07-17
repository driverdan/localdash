## 1. Backend: config + AirNow parser

- [x] 1.1 Add `airnow_api_key: str = ""` to `Settings` in `app/config.py` (env `AIRNOW_API_KEY`;
      empty disables the AirNow fetch), documented alongside the weather settings
- [x] 1.2 Create `app/weather/airnow.py` with `parse_airnow(payload) -> dict | None`: pick the
      max-AQI entry across pollutants, skip missing/negative AQI values, return
      `{value, category, category_name, pollutant}` or `None` for empty/all-invalid input
- [x] 1.3 Add an AirNow current-observations fixture (O3 + PM2.5 entries with differing AQI) and
      offline tests for `parse_airnow`: max-across-pollutants, -999 sentinel skipped, empty
      array → `None`

## 2. Backend: service integration

- [x] 2.1 Add `_fetch_aqi()` to `WeatherService` (`app/weather/service.py`): return `None`
      without a request when `airnow_api_key` is empty; otherwise GET the AirNow
      current-observations endpoint (lat/lon from settings, `distance=25`, `format` JSON, key as
      `API_KEY`), `raise_for_status()`, shape via `parse_airnow`, log-and-return-`None` on any
      failure
- [x] 2.2 Join `_fetch_aqi` to the `asyncio.gather` in `_refresh` and add `aqi` to the returned
      payload; keep the both-NWS-failed error check ignoring AQI (AQI success never rescues,
      AQI failure never breaks)
- [x] 2.3 Service tests with `httpx.MockTransport`: payload carries `aqi` when AirNow responds;
      `aqi: null` with empty key (and no AirNow request recorded); AirNow 401 → `aqi: null`
      with NWS halves intact; both NWS fetches failed + AirNow ok still raises

## 3. Frontend: payload type + AQI chip

- [x] 3.1 Extend the `Weather` types in `frontend/src/features/home/api.ts` with
      `aqi: WeatherAqi | null` (`value`, `category`, `category_name`, `pollutant`)
- [x] 3.2 Render the AQI chip in `WeatherStrip.svelte`: compact pill reading
      "AQI {value} · {category_name}", background from a local category→EPA color map
      (1 `#00e400`, 2 `#ffff00`, 3 `#ff7e00`, 4 `#ff0000`, 5 `#8f3f97`, 6 `#7e0023`) with
      per-background black/white text; renders whenever `aqi` is non-null, including when
      `current` is null; nothing rendered when `aqi` is null

## 4. Verify

- [x] 4.1 Run backend tests (`pytest`) and frontend checks (`svelte-check`/build) clean
- [x] 4.2 Rebuild via `sg docker -c 'docker compose up --build -d'` and confirm
      `/api/v1/weather/current` carries a populated `aqi` with the real key, and the chip
      renders on the home page
