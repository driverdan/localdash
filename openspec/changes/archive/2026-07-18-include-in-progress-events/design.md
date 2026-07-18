## Context

`GET /api/v1/events/items` applies `upcoming` (default true) as `starts_at >= now()`
(`app/api/events.py`). The Events page and the homepage digest both call the endpoint without the
parameter, so an event vanishes from both the instant it starts. In the live database, 88% of
events carry an `ends_at`; the rest have none (some sources report no end time). Stored durations
are all under a day.

## Goals / Non-Goals

**Goals:**
- Keep events visible in the default (`upcoming=true`) listing until they end.
- Change exactly one predicate; both frontend consumers pick up the behavior for free.

**Non-Goals:**
- No invented end times: events without `ends_at` are not given a grace window.
- No frontend changes — no "happening now" badge or visual distinction for in-progress events
  (possible follow-up).
- No changes to ordering, `upcoming=false`, other filters, ingestion, or retention.

## Decisions

**Predicate: `coalesce(ends_at, starts_at) >= now()`.** For events with an end time this keeps
them until they end; for events without one it degenerates to today's `starts_at >= now()`, so
their behavior is unchanged. One expression covers both cases with no OR-branching.

- *Alternative — grace window for null `ends_at`* (e.g. treat as start + 3 hours): keeps the ~12%
  of end-less events visible while plausibly still running, but shows events that may have ended
  and encodes a made-up duration in the API. Rejected in favor of honest data; the gap is better
  closed at the sources.
- *Alternative — new `include_in_progress` parameter*: preserves old semantics behind opt-in, but
  both consumers want the new behavior and nothing external depends on the old one. Needless
  surface.

**Ordering unchanged (start time ascending).** In-progress events sort before not-yet-started
ones, which is the desired "happening now first" reading. With many simultaneous in-progress
events the 5-row homepage digest may show only in-progress events; that is accepted as correct
for a local dashboard.

**Parameter keeps its name.** `upcoming` now means "not yet ended"; only its description text and
the spec wording change. Renaming would touch clients for no behavioral gain.

## Risks / Trade-offs

- [Bad source data: an event with a far-future `ends_at` would pin itself to the top of the list
  for its whole duration] → Accepted; current data has no duration over a day, and dedup/ingest
  already normalizes times. Revisit with a duration cap only if it actually occurs.
- [`coalesce(ends_at, starts_at)` cannot use the `starts_at` index] → Irrelevant at current scale
  (hundreds of rows, single-table scan is microseconds).
