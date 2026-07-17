## Why

AQI intermittently disappears from the weather strip. The AQI half of the weather
payload has no independent persistence or last-good fallback: when the AirNow fetch
alone fails (transient 5xx, the shared 10s timeout, a top-of-hour empty `[]` array, or
an all-sentinel hour), `_fetch_aqi` returns `None`, the refresh still *succeeds*, and
that `None` overwrites a perfectly good cached AQI for the full cache TTL (default
10 minutes). The existing stale-serve fallback only fires when the whole refresh raises
(both NWS halves down), so it never protects the AQI half on its own.

## What Changes

- When a refresh produces `aqi: null` but the previously cached payload carried an AQI,
  carry the previous AQI forward instead of blanking it — the per-half analogue of the
  existing stale-serve behavior. This applies to both on-demand and scheduled refreshes.
- Bound the carry-forward by a max age so a long AirNow outage eventually lets the AQI
  drop to `null` rather than showing an indefinitely stale reading.
- Add an observation timestamp to the shaped `aqi` object (from AirNow's
  `DateObserved`/`HourObserved`). This is what the max-age bound is measured against, and
  it lets the UI show the AQI's age the way current conditions already show "as of".
- Surface the AQI's observation time in the weather strip (optional "as of" affordance on
  the chip), consistent with how station observations are already labeled.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `weather`: the AirNow AQI contract gains a last-good carry-forward on partial (AirNow-only)
  refresh failure, bounded by a max age; the shaped `aqi` object gains an observation timestamp.

## Impact

- `app/weather/airnow.py` — `parse_airnow` shape gains an observation timestamp field.
- `app/weather/service.py` — `WeatherService._refresh` / `get_current` carry forward the prior
  AQI when a fresh one is unavailable and the prior is within the max age; needs a small amount
  of retained state (or reuse of the retained payload) plus a max-age setting.
- `app/config.py` — a max-age setting for how long a last-good AQI may be served.
- `app/api/weather.py` — response `aqi` shape gains the timestamp field (additive, non-breaking).
- `frontend/src/features/home/api.ts` — `Aqi` type gains the timestamp field.
- `frontend/src/features/home/components/WeatherStrip.svelte` — optional AQI age display.
- `tests/test_weather.py` — new cases for carry-forward, max-age expiry, and the timestamp shape.
- `openspec/specs/weather/spec.md` — AirNow AQI contract requirement updated.
