## Context

`NominatimGeocoder` (`app/events/geocoding.py`) issues one HTTP request per `geocode()` call
with no pacing. The ingest pipeline (`app/events/ingest.py`) only calls it on a
`geocode_cache` miss, so steady-state volume is near zero, but onboarding a new source can
produce hundreds of back-to-back uncached lookups in one refresh cycle. The public Nominatim
usage policy allows an absolute maximum of 1 request/second; violating it can get the client
blocked. A single geocoder instance is constructed per refresh cycle
(`app/events/refresh.py`) and calls are awaited sequentially by the ingest loop today, but
nothing enforces spacing if callers ever overlap.

## Goals / Non-Goals

**Goals:**
- Guarantee outbound Nominatim requests are spaced at least a configurable minimum interval
  apart (default 1s), including under concurrent callers.
- Keep the throttle entirely inside `NominatimGeocoder` — no changes to ingest, cache, or
  source code paths.
- Allow the interval to be tuned (or set to 0 to disable) for a future self-hosted instance.

**Non-Goals:**
- No retry/backoff on 429s or failures (failures already resolve to `None` and are cached).
- No cross-process or cross-restart rate coordination — refresh cycles are minutes apart,
  and a single process owns all geocoding.
- No change to the per-request `httpx.AsyncClient` construction.

## Decisions

### 1. In-class slot reservation with `asyncio.Lock` + monotonic clock

`NominatimGeocoder` gains `min_interval: float = 1.0`, an `asyncio.Lock`, and a
"next allowed send time" measured with `time.monotonic()`. Each `geocode()` call briefly
holds the lock to claim the next send slot (`slot = max(now, next_slot)`; then
`next_slot = slot + min_interval`), releases the lock, sleeps until its slot, and sends.

- Correct under concurrency: slots are reserved atomically, so overlapping callers space out
  rather than stampede; the HTTP call itself happens outside the lock.
- `min_interval <= 0` skips the wait entirely (self-hosted / test escape hatch).
- *Alternative — hold the lock across the HTTP request*: simpler, but serializes on request
  latency (spacing becomes `interval + latency`), and buys nothing since request-start
  spacing is what the policy measures.
- *Alternative — `aiolimiter` or similar*: a dependency for ~10 lines of code; a token
  bucket's burst allowance is exactly what the 1 rps absolute cap forbids.

### 2. Configuration: `events_geocoder_min_interval_seconds` in `Settings`

Float, default `1.0`, wired through `app/events/refresh.py` when the geocoder is built —
same pattern as `events_geocoder_user_agent`. Env override
`EVENTS_GEOCODER_MIN_INTERVAL_SECONDS` comes free from pydantic settings.

### 3. Throttle state is per-instance

A fresh geocoder per refresh cycle means the first request of a cycle is never delayed and
cycles cannot violate the cap (they are scheduled minutes apart). No module-level state.

## Risks / Trade-offs

- [Long first-time ingest: N uncached addresses ≈ N seconds] → Acceptable: refresh runs as a
  background job; the permanent cache makes it a one-time cost per source.
- [Tests get slow if they hit the real throttle] → Unit tests use `min_interval=0` or small
  values and assert on captured send times / fake clock rather than sleeping ~seconds.
- [Per-instance state means a misconfigured second geocoder instance could double the rate]
  → Only `refresh.py` constructs one; not worth global state today.
