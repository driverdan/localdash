## Context

`reconcile_events()` (`app/events/ingest.py`) loads only events with
`Event.starts_at >= datetime.now(timezone.utc)`, buckets them by UTC date, and merges duplicates
within each bucket. The three reconcile tests in `tests/test_events_ingest.py` seed events with
`seed_event(title, start, ...)` on fixed dates: 2026-12-08 22:00, 2026-12-09 22:00, and
2026-12-10 13:00 UTC. After those times pass, the pass loads nothing, so `merged == 1` and the
single-event unpacking `(event,) = ...` fail.

Every other fixed date in the file reaches the database through `upsert_raw_events()`, whose
matching tiers compare events only with each other (same UTC day, ±fuzzy window), never with the
clock. The July–September 2026 dates there are already past and still pass, which confirms this.
Source-parser tests elsewhere (for example `tests/test_events_chattzoo.py`) already inject a fixed
`NOW`, so they are not affected either.

## Goals / Non-Goals

**Goals:**
- The three reconcile tests pass on any run date.
- Each test keeps what it checks today: events sharing one start time, in one UTC-day bucket, in
  the same UTC hour (the stale-key test depends on matching canonical keys, which are hour-bucketed).

**Non-Goals:**
- Changing `reconcile_events()` or its "upcoming only" filter.
- Converting the de-duplication tests' fixed dates, or adding a clock-freezing dependency.

## Decisions

**Relative dates from a helper, not a frozen clock.** Add to `tests/test_events_ingest.py`:

```python
def upcoming(days: int, hour: int) -> dt.datetime:
    """An hour-aligned UTC start `days` from today, always in the future."""
    day = dt.datetime.now(UTC) + dt.timedelta(days=days)
    return day.replace(hour=hour, minute=0, second=0, microsecond=0)
```

and replace each `start = dt.datetime(2026, 12, N, H, 0, tzinfo=UTC)` with `start = upcoming(30, H)`,
keeping each test's original hour (22, 22, 13). With `days >= 1` the result is at least the start of
tomorrow (UTC), so it is always after `now()`. Within a test both seeded events share the same
`start`, so they always land in the same UTC-date bucket and the same hour, wherever the run falls
relative to midnight.

Alternative considered: freezing time (`freezegun`/`time-machine`) or patching `datetime` in
`app.events.ingest`. Rejected: it adds a test dependency, or module-level `datetime` patching that
breaks silently if `ingest.py` changes how it imports `datetime`, to fix three lines.
Alternative considered: giving `reconcile_events()` an injectable `now` parameter. Rejected for this
change: it alters application code to fix a test-only problem; the relative-date helper is enough.

**Fixed dates stay where the clock doesn't matter.** The de-duplication tests keep their
December 3–6/12 dates. Fixed dates there are deterministic and readable, and the code they exercise
never compares against now. A one-line comment above the reconcile section notes why those tests
use `upcoming()` and the rest don't. Converting all December dates was considered for consistency
but would only add churn.

## Risks / Trade-offs

- [The reconcile tests no longer use the same dates on every run] → The dates only need to be in
  the future and shared within a test; nothing asserts on the date itself. Hour alignment keeps
  canonical keys and day buckets stable.
- [A new now-filtered test could still be written with fixed dates] → The added test-isolation
  requirement records the rule, and the helper is in the same file for reuse.
