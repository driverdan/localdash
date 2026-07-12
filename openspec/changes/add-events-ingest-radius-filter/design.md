## Context

`upsert_raw_events()` (`app/events/ingest.py`) stores every raw event a source returns: new
canonical keys are geocoded and inserted; existing keys are merged. There is no geographic gate
anywhere between source and DB. Geography only appears at read time — `app/api/events.py`
supports `max_miles` measured from `CHATTANOOGA_CENTER = (35.0456, -85.3097)`
(`app/events/__init__.py`) — so far-away events are hidden, not excluded: they still cost a
rate-limited Nominatim lookup (once per address, thanks to `GeocodeCache`) and a permanent
`events` row (events are never purged).

The companion change `add-tn-car-events-ical-feed` adds a statewide feed that is ~80%
non-Chattanooga, which turns this from theoretical into a real pollution problem. The filter is
designed as a general capability for any regional source, not something feed-specific.

Constraints:
- Sources emit addresses, never coordinates (spec: "Sources supply addresses, not coordinates"),
  so distance can only be known **after** geocoding — the filter cannot live in the sources.
- Geocoding failures must not fail ingest, and ungeocodable events are stored with null
  location (existing spec behavior we must not regress).
- `POST /api/v1/events/refresh` returns `run_sources()`'s stats dict verbatim (`app/api/events.py`
  line 93-96), so a new stats key flows to the API with no endpoint change.

## Goals / Non-Goals

**Goals:**
- Drop new events whose geocoded location is farther than a configurable radius from the
  Chattanooga center, before they are inserted.
- Keep the default deployment behavior sensible (100 mi, covering the greater Chattanooga
  region while still cutting off the far-flung statewide entries that motivated this filter)
  while letting a deployment disable the gate (`events_ingest_max_miles=0`).
- Make drops observable: a `skipped_far` stats count and a log line.

**Non-Goals:**
- No retroactive cleanup of already-stored far events (a one-off SQL delete is an operator
  task, not code).
- No change to the merge path: an existing event that later geocodes to a far location keeps
  its row (it was admitted under the rules in force at insert time; re-litigating stored rows
  adds complexity for a rare case).
- No per-source radius overrides — one global knob until a real need appears.
- No change to read-API filtering, geocoder throttling, or `GeocodeCache` semantics.

## Decisions

### 1. Filter lives in `upsert_raw_events()`, on the new-event path only

After the existing `_geocode(...)` call for a new canonical key: if coords were resolved and
the distance from `CHATTANOOGA_CENTER` exceeds the configured radius, count it, log at debug,
and `continue` — no `Event`, no tags, no link. The merge branch is untouched.

- *Alternative — filter in each source's `fetch()`*: rejected; sources have addresses, not
  coordinates, and it would duplicate the gate per source, defeating "adding a source touches
  nothing else".
- *Alternative — filter in `run_sources()` before upsert*: rejected; it would have to geocode a
  second time or restructure geocoding out of `upsert_raw_events()`, and the dedup lookup
  (is this key new?) lives inside the upsert loop.
- Ordering note: the drop check runs **before** the link-upsert block at the bottom of the loop
  body, so a dropped raw contributes nothing (the current loop tail runs for both branches —
  the implementation must `continue` past it).

### 2. Unlocated events are kept

No address, geocoder failure, or cached failed lookup → event is stored with null location,
exactly as today. Rationale: we cannot prove such an event is far, and the read API already
excludes unlocated events whenever a `max_miles` bound is applied. Dropping them would silently
lose genuinely local events with sloppy venue strings.

### 3. Configuration: `events_ingest_max_miles: float = 100` with `0` = disabled

New pydantic-settings field in `app/config.py` next to the other `events_*` knobs. `0` (or any
non-positive value) disables filtering — chosen over `None` because env-var plumbing of "unset
vs empty" through pydantic-settings is noisier than a numeric sentinel, and 0 miles is
meaningless as a real radius. Default 100 is deliberately broader than the fetch-time
`MEETUP_RADIUS_MILES = 50` (the Meetup source's own API search radius, which stays unchanged):
the ingest gate is a backstop for sources whose fetch returns statewide results, so a wider
catchment than the per-source fetch radius is intentional — it admits the greater Chattanooga
region (Cleveland, Dalton, …) while still rejecting the Memphis/Clarksville/Nashville entries
that motivated this change.

Plumbing: `upsert_raw_events()` and `run_sources()` gain a `max_miles: float = 0` keyword
(default = disabled, so existing tests and direct callers are unaffected); `refresh()`
(`app/events/refresh.py`) passes `settings.events_ingest_max_miles`. This keeps ingest free of
a `get_settings()` import, consistent with how the geocoder is injected today.

### 4. Distance math: haversine in Python

A small module-level `_haversine_miles(a: Coords, b: Coords) -> float` in `ingest.py`
(earth radius 3958.8 mi). Coords are already floats in hand at the check site; a PostGIS
`ST_Distance` round trip per event would add DB chatter for no accuracy we need at a 50-mile
scale. Origin is the existing `CHATTANOOGA_CENTER` constant (imported from `app.events`) —
not a new setting; the read API hardcodes the same origin as its default.

### 5. Observability: `skipped_far` in the stats dict

`upsert_raw_events()` returns `{"created": ..., "merged": ..., "skipped_far": ...}`. The key is
always present (0 when the filter is disabled) so the shape is stable. `refresh()`'s summary
log line gains the count, and the untouched `POST /api/v1/events/refresh` endpoint exposes it
automatically.

## Risks / Trade-offs

- [Bad geocode drops a genuinely local event] → Only events that *successfully* geocode far are
  dropped; unlocated ones are kept. 100 mi default is generous relative to the read API's
  typical `max_miles`. The address's `GeocodeCache` row records what Nominatim said, so the
  drop is diagnosable.
- [Dropped events are re-evaluated every cycle] → Acceptable: the address hits `GeocodeCache`
  (DB, not Nominatim), so repeat cost is one cache read per address per cycle — exactly the
  cost the cache was built for. `skipped_far` will therefore stay non-zero on every cycle for a
  statewide feed; that is expected, not a leak.
- [Dropped events still create `GeocodeCache` rows] → Intended: the cache is permanent by spec
  and is what makes the repeat evaluation cheap.
- [A cross-source duplicate could be dropped from one source but created by another] → Not
  possible in a divergent way: the gate keys off the geocoded address of the raw being
  inserted; if the first raw is dropped, the key does not exist, and the second source's raw is
  evaluated fresh on its own address. Two sources for the same real event resolve to the same
  area, so the outcome is consistent.
- [Radius change does not re-admit previously dropped events retroactively... it does] → Since
  nothing is stored for dropped events, loosening the radius simply admits them on the next
  cycle (sources re-report upcoming events). Tightening it does not remove already-stored rows
  (see Non-Goals).
