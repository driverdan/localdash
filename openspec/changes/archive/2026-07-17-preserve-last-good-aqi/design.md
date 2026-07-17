## Context

The weather feature proxies NWS conditions/forecast plus an AirNow AQI into one shaped
payload behind an in-process TTL cache (`WeatherService`, `app/weather/service.py`). A
refresh runs three fetches concurrently — forecast, station observation, AQI — via
`asyncio.gather`. The three fail independently: each `_fetch_*` catches its own exception and
returns `None`. `_refresh` only raises when **both** NWS halves are `None`; that raise is what
triggers the existing stale-serve fallback in `get_current` (serve the prior `self._payload`).

The AQI half has no equivalent protection. When AirNow alone fails, `_fetch_aqi` returns `None`,
`_refresh` returns a successful payload with `aqi: None`, and that payload replaces
`self._payload` — discarding a good prior AQI for the whole TTL. AirNow returns no usable AQI
routinely: a top-of-hour empty `[]`, an all-`-999` hour, the shared 10s timeout, or a transient
5xx all collapse to `None`. The scheduled proactive refresh (per the `weather` spec) goes through
the same `_refresh`, so it exhibits the same blanking.

The shaped `aqi` object today carries `value`, `category`, `category_name`, `pollutant` — but no
timestamp, so there is nothing to bound staleness against or to show the reading's age.

## Goals / Non-Goals

**Goals:**
- Stop a partial (AirNow-only) refresh failure from discarding a good cached AQI.
- Bound how stale a carried-forward AQI may be, then let it drop to `null`.
- Give the `aqi` object an observation timestamp for the bound and for UI display.
- Keep `parse_airnow` a pure, offline-testable function of its payload.

**Non-Goals:**
- Decoupling AQI into its own cache/TTL (Option 2 from exploration) — larger refactor, not needed.
- Retrying AirNow or widening the search radius (Option 3) — separate concern.
- Changing NWS fetch/stale behavior.

## Decisions

### Carry-forward lives in `get_current`, comparing against the retained payload
`get_current` already holds the prior payload in `self._payload` at the moment `_refresh`
returns. When the fresh payload's `aqi` is `None` and `self._payload`'s `aqi` is non-`None` and
within the max age, copy the prior `aqi` into the fresh payload before storing it. No new
retained field is required — the prior AQI (with its `observed_at`) already lives in the cached
payload. The age bound is computed from that `observed_at`, not from fetch time, so the guarantee
is about how old the *reading* is, matching the spec.

*Alternative considered:* a dedicated `self._last_aqi` slot. Rejected — redundant with
`self._payload`, and a second source of truth to keep in sync.

### `observed_at` is derived in `parse_airnow` from AirNow's date/hour/zone fields
AirNow current-observation entries carry `DateObserved` (e.g. `"2026-07-17"`), `HourObserved`
(int, local), and `LocalTimeZone` (e.g. `"EST"`). `parse_airnow` composes these into an
ISO-8601 `observed_at` on the winning entry, keeping the function pure and fixture-testable. The
LocalTimeZone abbreviation is mapped to a fixed UTC offset via a small lookup of the values
AirNow actually emits (standard-time US zones). If the abbreviation is unknown, `observed_at` is
still emitted as a naive local timestamp for display, and the service treats an unparseable
offset as "assume fresh enough to show, but fall back to fetch-time age for the bound" (see
Risks). For Chattanooga this is Eastern, always resolvable.

*Alternative considered:* bound staleness by fetch time (monotonic clock at last good AQI)
instead of observation time. Simpler (no tz parsing) but weaker — it would happily show a reading
that was already an hour stale when fetched. We still keep fetch-time as the fallback path only.

### Max age is a setting, defaulting to 120 minutes
`airnow_stale_minutes` (env `AIRNOW_STALE_MINUTES`, default 120). AirNow observations are hourly,
so 120 minutes tolerates a missed hour plus a top-of-hour gap while still dropping a clearly
dead feed. Lives beside `weather_cache_minutes` in `config.py`.

### Timestamp is additive on the API and frontend
The `aqi` object gains `observed_at` (nullable string). The FastAPI response is untyped dict
pass-through, so no server-side schema change beyond shaping. The frontend `Aqi` type gains
`observed_at: string | null`; `WeatherStrip.svelte` may render an "as of" affordance on the chip,
mirroring the existing `fmtAsOf` used for station observations. Non-breaking for any client that
ignores the new field.

## Risks / Trade-offs

- **AirNow timezone abbreviations are irregular** → Map the concrete set AirNow returns (the
  app only ever queries one fixed coordinate, so in practice one zone). Unknown abbreviations
  fall back to a display-only naive timestamp plus fetch-time age bounding, so a parse gap
  degrades gracefully rather than crashing shaping.
- **A carried-forward AQI can look "current" in the chip** → The `observed_at` "as of" label is
  the mitigation; a reading pinned at an old time signals its age the same way stale station
  conditions already do.
- **Bound is on observation time, so a fast-fetched-but-old reading still ages out correctly**,
  but clock skew between the AirNow station's zone and the server is possible → offsets are
  fixed and the tolerance (120 min) dwarfs any plausible skew.
- **Scheduled refresh interaction** → carry-forward is in `get_current`/`_refresh`, the shared
  path, so the scheduled refresh inherits it automatically; the broadcast-on-change logic
  compares shaped payloads, and a carried-forward AQI keeps the payload equal, so no spurious
  `weather` ping fires.

## Migration Plan

Pure additive behavior change, no data model or migration. Deploy is a rebuild. Rollback is
reverting the change — the `aqi` object simply loses `observed_at` and reverts to blanking on
AirNow failure. New setting has a safe default, so `.env` needs no change (document it in
`.env.example`).

## Open Questions

- Should the UI show the AQI "as of" time always, or only once it diverges from the current
  conditions' observation time (i.e. only when actually carried forward)? Leaning: always, for
  consistency with station conditions — but low-stakes, resolve in review.
