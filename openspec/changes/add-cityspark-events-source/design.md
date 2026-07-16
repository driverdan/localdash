## Context

The events pipeline is **fetch sources → ingest (dedup + tag + geocode) → serve**. Its source
contract, `RawEvent`, is deliberately minimal: title, start time, source name/URL, plus optional
description, end time, venue name, address, and source event id. Coordinates are explicitly excluded.
That is not an oversight — it is a stated convention, documented in `app/events/sources/base.py` and
restated at `app/events/sources/meetup.py:9`:

> "In keeping with the rest of the pipeline, only an address is emitted per event; coordinates are
> derived later by the ingest pipeline's geocoder."

Tagging follows the same shape: `app/events/tagging.py` guesses topics by keyword-matching title and
description against an 11-topic map.

Both conventions assume sources are *impoverished* — that they know a place name and little else, so
the pipeline must derive the rest. Every source registered today fits that assumption. CitySpark
breaks it. Its payload states, per event, exactly what the pipeline works to infer:

| Signal | Pipeline derives it by | CitySpark states it | Coverage (n=526) |
|---|---|---|---|
| Coordinates | Nominatim geocoding @ 1 req/sec | `latitude` / `longitude` | 526/526 (100%) |
| Topics | keyword match on title+description | `Tags` (curated ids) | 520/526 (99%) |

Honoring the current convention would mean discarding both and re-deriving them — worse, and at
cost. This design revises the convention rather than special-casing one source.

## Goals / Non-Goals

**Goals:**

- Ingest The Pulse's CitySpark calendar via its JSON API.
- Let a source supply coordinates and tags it already knows, without the pipeline re-deriving them.
- Keep every existing source byte-for-byte behaviorally unchanged.
- Keep the tag vocabulary coherent across sources that supply tags and sources that don't.
- Correct UTC handling, verified by test.

**Non-Goals:**

- Changing `MeetupSource` to request coordinates (a clear follow-up; not here).
- Rolling CitySpark's tag hierarchy up to its 23 roots — the user chose the event's own tags as-is.
- Changing storage, migrations, API routes, scheduler, or frontend.
- Any keyword tagging of CitySpark events.
- Reconciling the volume shift in the UI (the API already paginates and filters).

## Decisions

### 1. The design spine: the pipeline derives only what the source does not supply

Both contract changes are one principle, applied twice:

```
                      supplied?
  coords:   RawEvent.latitude/longitude ──yes──► use as-is
                      │no
                      └──────────────────────────► geocode(address)   [unchanged path]

  tags:     RawEvent.tags ──────────────yes──► lowercase, use as-is
                      │no
                      └──────────────────────────► tag_event(title, description)  [unchanged path]
```

Both fields are **optional and default to absent**, so a source that says nothing gets exactly
today's behavior. This is what makes the change additive in practice despite revising a stated
convention: the fallback branch *is* the current code path.

*Alternative considered — keep the convention, special-case CitySpark inside ingest.* Rejected: it
puts source-specific knowledge into `ingest.py`, which the architecture explicitly keeps
source-agnostic ("Adding a source MUST require only a new source class plus its registration").

*Alternative considered — geocode CitySpark addresses anyway, for consistency.* Rejected on three
counts: ~8 minutes of Nominatim traffic per cold cycle at the mandated 1 req/sec; strictly worse
coordinates than the venue's own; and degraded dedup (below).

### 2. Coordinates are load-bearing for de-duplication, not just for the map

`dedup.events_match` treats location as a **hard gate**:

> "When both sides are geocoded their coordinates decide (venue strings like 'Sonic' repeat across
> cities); venue/address text equality applies only when coordinates are missing on at least one
> side. With no location evidence at all, this never matches."

CitySpark is an aggregator-of-aggregators — it carries library, Bandsintown, and similar listings —
so it *will* overlap the existing Meetup and iCal sources. Merge quality therefore depends directly
on coordinate quality on both sides. Supplying exact venue coordinates makes the largest source in
the system also the best-behaved one for dedup. Re-geocoding would actively harm this.

### 3. `StartUTC`, never `DateStart` — the payload's `Z` lies

Verified live:

```
Teen Artist Showcase   DateStart = 2026-07-15T08:00:00Z   ← "Z", but actually 08:00 EDT
                       StartUTC  = 2026-07-15T12:00:00Z   ← true UTC ✓ (= 08:00 EDT)
```

`DateStart`/`DateEnd` carry a `Z` suffix on what is local time. Using them shifts every event by the
UTC offset (4h in EDT), which corrupts `dedup.canonical_key` — built from normalized title + start
**hour** — and breaks cross-source dedup against correctly-dated sources. `StartUTC`/`EndUTC` are
authoritative and 526/526 populated.

This is the same class of bug the `CarCruiseFinder` source already documents (its detail pages carry
`-05:00` offsets on August dates, which is why only the listing page is parsed). Two independent
sources now, so this gets an explicit module docstring warning and a dedicated regression test.

### 4. Lowercase source-supplied tag names

`Tag.name` is `String(64)`, `unique=True`; Postgres is case-sensitive. CitySpark's `"Music"` and
keyword tagging's `"music"` would become two rows — a fragmented vocabulary where
`GET /api/v1/events/items?topic=music` silently misses every CitySpark event, and
`GET /api/v1/events/tags` lists both. Five names collide case-insensitively: `family`, `food`,
`music`, `nightlife`, `sports`.

Lowercasing on ingest merges them into the existing vocabulary. Max observed CitySpark tag name is
24 chars, so `String(64)` needs no migration. Tag insertion must stay idempotent/race-safe
(on-conflict-do-nothing), consistent with how tags are created today.

*Alternative considered — roll up to the 23 hierarchy roots* (`AllTags` is a `{id,name,parent}`
tree; roots would yield ~15 topics, close to the existing 11). Rejected: the user explicitly chose
the event's own tags. Also, several roots are facets rather than topics (`Engagement Level`,
`Competitive Level`, `Attendance`, `Summary`, `Topics`), so a naive rollup would import junk. The
250 leaf names in use are more specific and directly useful.

### 5. API shape: always send `end`; paginate on `skip`

```
POST https://portal.cityspark.com/api/events/GetEvents/ChattanoogaPulse
{"ppid":9824,"start":"<ISO>","end":"<ISO>","distance":<mi>,"lat":..,"lng":..,
 "skip":<n>,"sort":"Time","search":"","category":[],"labels":[],
 "pick":false,"tps":null,"sparks":false,"defFilter":"all"}
→ {"Value":[…],"Success":true,"ErrorMessage":null,…}
```

- With `end` set, page size is **100**; with `end: null` the API returns only 25 events for a single
  day. **Always set `end`.**
- Paginate `skip` = 0, 100, 200…; stop when a page returns fewer than 100. Verified: 526 unique
  events over 14 days, terminating at `skip=500 → 26`.
- A bounded page cap guards against a pathological non-terminating loop.
- Plain client works: no auth, no referer, no UA spoofing.

**Radius and lookahead** become settings. The portal's own default is 25 mi centered at
`(35.0457984, -85.3093995)` — effectively `CHATTANOOGA_CENTER (35.0456, -85.3097)`. `MEETUP_RADIUS_MILES`
is 50. Default to the portal's 25 mi and a 14-day window: 25 mi is what The Pulse itself curates for
(widening past the portal's own radius invites listings its editors never intended to surface), and
14 days is the window measured at 526 events. Both are settings precisely because they are judgment
calls, and the existing `events_ingest_max_miles` filter still applies downstream.

### 6. Structure: pure parse function + thin async fetch

Mirrors `carcruisefinder.parse_listing` — a pure function over a captured payload, so tests run
offline with no network, per the source registry's "fixtures live in the test suite only" rule. The
tag id→name map (`AllTags`) is parsed alongside the events and resolved in the pure function.

Registration in `build_sources()` is gated by an enable setting (unlike CarCruiseFinder, which is
unconditional): this source is large enough that an operator may reasonably want it off.

## Risks / Trade-offs

- **[Undocumented internal endpoint of a commercial aggregator, read via The Pulse's `ppid 9824`]** →
  It may change or be restricted without notice. Nothing is circumvented (no auth, no WAF, no UA
  spoofing) and volume is a handful of paged POSTs per refresh. Breakage manifests as zero events
  plus logs, contained by `run_sources()`'s per-source failure isolation. Recorded plainly, in the
  same spirit as the CarCruiseFinder docstring's honesty about its own fragility.
- **[Revising a documented convention]** → The two conventions live in prose across
  `base.py`, `meetup.py:9`, and the `events` spec. Stale text is a real hazard: all three must be
  updated together, and the spec delta pins the new rule.
- **[Volume: CitySpark dominates the events table]** → Cycle cost moves from geocoding to dedup,
  which is O(candidates) per event and already bounded by the start-time window. Mitigated in part
  by the change itself: the biggest source adds ~zero Nominatim traffic.
- **[Payload shape drift — a field renamed upstream]** → The pure parse function fails loudly in
  tests against the fixture, and per-source isolation contains it at runtime. Events missing
  `StartUTC` are skipped with a warning rather than defaulting to `DateStart` (a silent 4h error is
  worse than a dropped event).
- **[Trade-off: 250 leaf tags vs 11 keyword topics]** → `GET /api/v1/events/tags` grows
  substantially and the frontend's topic filter gets a much longer list. Accepted per the user's
  explicit choice; the vocabulary is more specific and lowercasing keeps the two vocabularies
  merged rather than parallel. Trimming to a curated subset stays available later.
- **[Supplied tags bypass keyword tagging entirely]** → A CitySpark event tagged only
  `"visual arts"` will not also pick up `arts` from keywords, so cross-source topic filters can
  behave unevenly between sources. This is the direct consequence of "use whatever tags are included
  with the event" and is accepted deliberately.
