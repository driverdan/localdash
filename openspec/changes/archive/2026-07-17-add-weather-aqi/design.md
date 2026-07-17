## Context

The weather feature (`app/weather/`) proxies NWS behind an in-process TTL cache: `_refresh()`
runs the forecast and observation fetches concurrently, the two halves fail independently, and
only a fully-empty result is an error. Shaping is pure functions in `app/weather/nws.py` tested
offline against fixtures. The frontend consumes the whole payload in one fetch
(`frontend/src/features/home/api.ts` → `WeatherStrip.svelte`) and refetches on the `weather`
ws ping. AirNow's current-observations endpoint
(`GET https://www.airnowapi.org/aq/observation/latLong/current/`) is a single keyed call —
`format=application/json`, `latitude`/`longitude`, `distance` (miles), `API_KEY` — returning an
array of per-pollutant observations (`ParameterName`, `AQI`, `Category.{Number,Name}`), updated
hourly.

## Goals / Non-Goals

**Goals:**
- Current overall AQI in the weather payload and widget, with EPA category color.
- Zero behavior change when `AIRNOW_API_KEY` is unset: no upstream call, `aqi: null`, widget
  renders exactly as today.
- AQI failures never degrade the NWS halves or trip the cold-cache 502.

**Non-Goals:**
- AQI forecasts (AirNow has a forecast endpoint; not used here).
- Per-pollutant breakdown in the UI, historical AQI, or AQI on the map/anywhere else.
- A separate cache TTL or scheduler job for AQI — it rides the weather cache as-is, accepting
  that a 10-minute TTL polls an hourly feed.

## Decisions

**AQI joins the existing payload, not a new endpoint.** The widget is one fetch, one cache, one
ping; a third top-level key (`aqi`) beside `current`/`periods` means the frontend change is a
type extension plus markup, and the scheduler's changed-payload ping covers AQI updates for
free. Alternative — `/api/v1/weather/aqi` — rejected: two fetches and two error states in the
widget for no isolation benefit the independent-halves pattern doesn't already give.

**Fetch joins `_refresh()` as a third `asyncio.gather` member.** `_fetch_aqi()` returns
`dict | None`, logging and swallowing errors like `_fetch_periods`/`_fetch_current`. The
"both NWS fetches failed" error check is unchanged — AQI is additive and never makes an
otherwise-failed refresh succeed (an AQI-only payload would render an empty-looking widget) nor
an otherwise-successful one fail. With an empty `airnow_api_key`, `_fetch_aqi` returns `None`
without a request.

**Same httpx client, no discovery.** AirNow needs no metadata hop; the NWS client's
`Accept: application/geo+json` header is ignored by AirNow (shape is forced by the `format`
query param) and the identifying User-Agent is harmless, so `_fetch_aqi` reuses the client
`_refresh` already opened. The key travels as the `API_KEY` query param; `distance=25` miles
matches the app's Chattanooga-radius conventions (e.g. CitySpark).

**Shaping is `parse_airnow(payload) -> dict | None` in a new `app/weather/airnow.py`.** Keeps
`nws.py` single-source. Overall AQI is the max-`AQI` entry across pollutants (EPA convention:
the reported AQI is the worst pollutant, which is the "primary" one). Entries with missing or
negative `AQI` (AirNow uses -999 sentinels) are skipped; an empty or all-invalid array yields
`None`. Shape:

```json
{"value": 62, "category": 2, "category_name": "Moderate", "pollutant": "PM2.5"}
```

No `observed_at`: AirNow reports `HourObserved` + `LocalTimeZone` rather than an ISO instant,
the feed is hourly anyway, and the widget already shows the NWS observation time. Category
number (1–6) is the frontend's color key; the name is display text passed through verbatim.

**Frontend: colored chip next to the temperature.** `WeatherStrip.svelte` renders
`AQI {value} · {category_name}` as a small pill in the current-conditions row, background from a
local category-number → EPA color map (1 green `#00e400`, 2 yellow `#ffff00`, 3 orange
`#ff7e00`, 4 red `#ff0000`, 5 purple `#8f3f97`, 6 maroon `#7e0023`), with black/white text
chosen per background for contrast. Rendered only when `weather.aqi` is non-null. The chip
placement works even when `current` is null (AQI can outlive a failed NWS observation), so it
sits in the widget body gated only on `aqi` — anchored visually with the current row when both
exist.

**Config:** `airnow_api_key: str = ""` in `Settings` (pydantic-settings maps `AIRNOW_API_KEY`
automatically). No `airnow_enabled` flag — the key doubles as the switch, matching
`events_meetup_token`.

## Risks / Trade-offs

- [AirNow monitor gap: no station within `distance` returns an empty array] → shaping yields
  `None`; widget shows nothing rather than a misleading value. Chattanooga has O3 + PM2.5
  monitors, so this is a degraded-upstream case, not the norm.
- [Invalid/expired key returns an AirNow error body, not an exception-shaped response] →
  `_fetch_aqi` treats non-2xx as failure via `raise_for_status()`; AirNow returns 401-class
  statuses for bad keys, which lands in the existing log-and-`None` path.
- [10-min polling of an hourly feed wastes ~5 of 6 calls] → accepted: 6 req/hr against a
  500 req/hr key limit is negligible, and a separate TTL would complicate the single-cache
  design for no user-visible gain.
- [EPA chip colors (raw greens/yellows) may clash with the dashboard palette] → colors are the
  standardized AQI scale users recognize from every AQI product; keep them verbatim, confined
  to a small pill.

## Migration Plan

Pure addition: deploy backend + frontend together (`docker compose up --build`). Rollback is a
revert; absent key or reverted frontend both degrade to today's behavior. No data or schema
migration.

## Open Questions

None.
