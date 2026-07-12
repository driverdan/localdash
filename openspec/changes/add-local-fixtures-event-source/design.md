## Context

The events feature has a pluggable source interface (`app/events/sources/base.py`): a source
implements async `fetch() -> list[RawEvent]` and is registered in `build_sources()`
(`app/events/sources/__init__.py`); ingest handles dedup (canonical key = normalized title + UTC
start day-and-hour, `app/events/dedup.py`), tagging, geocoding (Nominatim + permanent cache), and
persistence. Existing sources (iCal, Meetup) all require an upstream feed or API.

Several flagship local events have no machine-readable feed of any kind (verified live):
Chattanooga Cars and Coffee (GoDaddy site builder — no iCal, no structured data), Riverside
Chattanooga, World of Wheels Chattanooga. The news feature's precedent for "upstream has no usable
interface, so code is the source of truth" is `app/news/registry.py` — a declarative in-code
registry. This change applies the same pattern to events.

One constraint conflicts with the current spec text: the events spec's pluggable-source
requirement forbids any "sample/fixture source" importable by the application. Its intent was to
ban fake demo data; a curated registry of *real* events is different in kind, so the requirement
is narrowed rather than violated (see the delta spec).

## Goals / Non-Goals

**Goals:**
- A `FixturesSource` (`app/events/sources/fixtures.py`) whose registry is code-as-config:
  declarative fixture entries with recurrence rules, expanded into concrete `RawEvent`s at each
  ingest run within a bounded upcoming horizon.
- Recurrence expansion as a pure function so it is unit-testable offline with injected windows.
- Seed the registry with the three verified car events; the mechanism stays generic.
- A config gate (`events_fixtures_enabled`, default true) consistent with existing source gating.
- No changes to ingest, storage, migrations, API, or frontend.

**Non-Goals:**
- No scraping of organizer sites, no admin UI for editing fixtures, no DB table for fixtures
  (unlike news, nothing downstream needs per-fixture rows — `RawEvent`s flow through the normal
  pipeline; a DB sync like `news/registry.py`'s can be added later if fixtures ever need health
  telemetry).
- No exception dates / cancellation handling (an organizer skipping one month is accepted drift).
- No coordinates in fixtures — addresses only, geocoded by the existing pipeline (spec rule).

## Decisions

### D1: Recurrence via `dateutil.rrule`, promoted to a direct dependency

Use `dateutil.rrule` for recurring fixtures — e.g. Cars and Coffee is exactly
`rrule(MONTHLY, byweekday=SU(3), bymonth=(3,...,11))`. `python-dateutil` is already installed as a
transitive dependency of `icalendar` (verified in the venv: 2.9.0.post0), so this adds zero
install weight; it is added to `pyproject.toml` explicitly because relying on a transitive dep for
a direct import is fragile.

*Alternative considered*: a hand-rolled "Nth weekday of month within month-range" helper. Rejected:
it re-implements calendar edge cases dateutil already handles, grows a second mechanism the moment
a fixture needs a different pattern, and saves nothing since the library is already present.

### D2: Two fixture shapes — recurrence rule, or explicit dates

A fixture entry (a small dataclass, mirroring the declarative style of `news/registry.py`'s
`SOURCES`) carries `slug`, `title`, `description`, `venue_name`, `address`, `source_url`, local
start/end times, and exactly one of:

- **`rule`** — an rrule for genuinely recurring events (Cars and Coffee).
- **`dates`** — explicit local dates for annual events whose next edition is only known once
  announced (World of Wheels was Jan 9–11 2026; Riverside runs multi-day in March). A
  year-agnostic rule ("second weekend of January") was rejected: organizers do not commit to such
  patterns, and a wrong auto-generated date is worse than a missing one. Explicit dates make the
  yearly-review obligation visible in the diff.

Multi-day events (`dates` entries) emit **one `RawEvent` per day** with that day's start/end
times, matching how attendees experience them and keeping dedup's day-granular canonical key
meaningful.

### D3: Local wall-clock times, converted to UTC per occurrence

Fixtures are declared in local wall-clock time (`America/New_York` via `zoneinfo`) because that is
what organizers publish ("8am–12pm"). Expansion runs the rrule over naive local datetimes, then
localizes each occurrence and converts to aware UTC — so 8am ET is correct on both sides of a DST
transition. `RawEvent.start_time`/`end_time` remain aware UTC per the source contract. `tzdata` is
already a transitive dep (icalendar) for platforms without a system zone database.

### D4: Bounded expansion horizon, stable per-occurrence ids

Each `fetch()` expands only occurrences in `[now, now + 90 days]`. Rationale: ingest volume stays
constant per run; already-ingested past occurrences persist in the DB (events are retained
indefinitely) so nothing is lost when they leave the window; 90 days always covers the next
edition of a monthly event and gives seasonal/annual events reasonable lead time.

Each occurrence gets a deterministic `source_event_id` of `<fixture-slug>-<local-date>` (e.g.
`chattanooga-cars-and-coffee-2026-08-16`), and its stable title + start also make repeat ingests
collapse via the existing canonical-key dedup — re-running every hour is idempotent.

The pure core is `expand(fixture, window_start, window_end) -> list[RawEvent]`;
`FixturesSource.fetch()` just computes the window from the clock and concatenates expansions, so
tests never depend on wall time.

### D5: Config gate defaults on; registration in `build_sources()`

`events_fixtures_enabled: bool = True` in `config.py`, checked in `build_sources()`. Default true
— unlike iCal/Meetup there is no URL or token to configure, no network I/O, and the data is real;
this mirrors `news_enabled=True` for the other code-as-config feature. The delta spec re-scopes
the old "no sources active by default" clause to *network* sources accordingly.

### D6: Staleness signal is an ingest-time log warning, not a failing test

The honest caveat: manual curation drifts when organizers change dates. Mitigations:

- Every emitted event's `source_url` is the organizer page, so users can always verify.
- At fetch time, any fixture yielding zero occurrences in the horizon **and** zero in the next
  366 days logs a warning naming the fixture — the operational "this entry needs its yearly
  review" signal. The staleness predicate itself is pure and unit-tested with injected clocks.

*Alternative considered*: a pytest "freshness tripwire" that fails when an annual fixture's dates
are all past. Rejected: it makes CI fail on calendar time with no code change, and would fail on
day one (both seeded annual events' 2026 editions predate today). Deliberately-stale explicit-date
entries are harmless — they emit nothing.

## Risks / Trade-offs

- **[Curation drift — dates change or events cancel]** → organizer `source_url` on every event;
  staleness warning (D6); registry edits are one-line diffs reviewed like any code change.
- **[Wrong future dates for annual events]** → explicit dates only, never extrapolated (D2); an
  unannounced edition is simply absent rather than wrong.
- **[Spec conflict with the fixture prohibition]** → resolved in the delta spec by narrowing the
  ban to sample/demo data and updating the "unconfigured registry" scenario to hold with fixtures
  disabled; not silently ignored.
- **[Geocoding load from new addresses]** → three venue addresses, each geocoded once ever via the
  existing permanent `geocode_cache`.
- **[DST edge cases in expansion]** → naive-local expansion + per-occurrence localization (D3),
  with a unit test spanning a DST boundary.
