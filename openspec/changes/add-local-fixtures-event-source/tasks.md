## 1. Dependency & config

- [ ] 1.1 Add `python-dateutil` to `pyproject.toml` dependencies (already installed transitively
      via icalendar — this promotes it to a direct dep since `fixtures.py` imports
      `dateutil.rrule`)
- [ ] 1.2 Add `events_fixtures_enabled: bool = True` to `Settings` in `app/config.py`, grouped
      with the other `events_*` knobs and commented like them

## 2. Fixtures source module

- [ ] 2.1 Create `app/events/sources/fixtures.py` with a `Fixture` dataclass: `slug`, `title`,
      `description`, `venue_name`, `address`, `source_url`, local start/end times
      (America/New_York via `zoneinfo`), and exactly one of `rule` (a `dateutil.rrule`) or
      `dates` (explicit local dates); validate the exclusivity in `__post_init__`
- [ ] 2.2 Implement pure `expand(fixture, window_start, window_end) -> list[RawEvent]`: run the
      rrule over naive local datetimes (or iterate explicit dates), keep occurrences inside the
      window, localize each and convert start/end to aware UTC, emit one `RawEvent` per day with
      `source_event_id = f"{slug}-{local_date.isoformat()}"`, `source_name` = the fixtures source
      name, and `source_url` = the organizer page
- [ ] 2.3 Implement pure `is_stale(fixture, now) -> bool` (no occurrence within `now + 366 days`)
- [ ] 2.4 Implement `FixturesSource(EventSource)` with `name = "Local fixtures"`: `fetch()`
      computes the `[now, now + 90 days]` window, concatenates `expand()` over the registry, and
      logs a warning naming each stale fixture (never raising); no network I/O anywhere
- [ ] 2.5 Add the `FIXTURES` registry seeded with the three verified entries (module docstring
      explains the code-as-config pattern, the manual-curation caveat, and the yearly-review rule
      for explicit-date entries):
      Chattanooga Cars and Coffee (rrule: 3rd Sunday monthly Mar–Nov, 8:00–12:00 local,
      Chattanooga State Community College, https://chattanoogacarsandcoffee.com/);
      Riverside Chattanooga (explicit March dates for the next announced edition — or last known
      if unannounced — Finley Stadium / First Horizon Pavilion,
      https://www.riversidechattanooga.com/);
      World of Wheels Chattanooga (explicit dates, 2026 edition Jan 9–11, Chattanooga Convention
      Center, https://worldofwheels.net/chattanooga/)

## 3. Registration

- [ ] 3.1 Register `FixturesSource` in `build_sources()` in `app/events/sources/__init__.py`,
      gated on `settings.events_fixtures_enabled`, and update that module's docstring listing of
      production sources
- [ ] 3.2 Confirm no other layer needs changes (ingest/dedup/tagging/geocoding/API/frontend are
      source-agnostic per the spec)

## 4. Tests (offline, pure)

- [ ] 4.1 `tests/test_events_fixtures.py`: rrule expansion — a Jul 1–Sep 29 window over the
      Cars-and-Coffee rule yields exactly the three 3rd-Sunday occurrences with correct fields
- [ ] 4.2 Out-of-season window (Dec–Feb) over a Mar–Nov rule yields zero events
- [ ] 4.3 DST correctness — 8:00 AM local occurrences on both sides of a transition map to 12:00Z
      (EDT) and 13:00Z (EST)
- [ ] 4.4 Explicit-date multi-day fixture in-window emits one `RawEvent` per day with per-day
      start/end times; out-of-window dates emit nothing
- [ ] 4.5 Deterministic `source_event_id` — expanding the same window twice yields identical ids
      (idempotent-ingest precondition), and ids follow `<slug>-<local-date>`
- [ ] 4.6 `is_stale` with injected clocks — true for an all-past explicit-date fixture, false for
      an active rrule fixture
- [ ] 4.7 Registry validity — every `FIXTURES` entry has a unique slug, non-empty
      title/address/source_url, and exactly one recurrence form
- [ ] 4.8 `build_sources()` gating — fixtures source present with defaults, absent with
      `events_fixtures_enabled=false` (and the no-config + fixtures-disabled combination builds an
      empty registry)

## 5. Verify

- [ ] 5.1 Run `pytest` — full suite green (DB-backed tests may auto-skip as documented)
- [ ] 5.2 Run a manual refresh against the local stack and confirm upcoming Cars and Coffee
      occurrences appear via `GET /api/v1/events/items` with tags/geocoding applied by the
      existing pipeline, and that a second refresh creates no duplicates
