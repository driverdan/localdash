## Why

Several of Chattanooga's best-known recurring events — most notably the flagship monthly
Chattanooga Cars and Coffee meet — publish no machine-readable feed at all (verified: no iCal, no
structured data on their GoDaddy/organizer sites), so the events feature can never surface them
through the existing iCal/Meetup sources. The news feature already solved the analogous problem
with code-as-config (`app/news/registry.py`: outlets declared in code, synced at runtime); the
events feature needs the same escape hatch for feedless real-world events.

## What Changes

- Add a **local fixtures event source**: a code-as-config registry of well-known recurring local
  events with no feed, expanded from recurrence rules into concrete `RawEvent`s on each ingest
  run within a bounded upcoming horizon (now → +90 days).
- Seed the registry with three verified car events (the mechanism itself is generic):
  - **Chattanooga Cars and Coffee** — 3rd Sunday monthly, March–November, 8am–12pm ET,
    Chattanooga State Community College (https://chattanoogacarsandcoffee.com/).
  - **Riverside Chattanooga** — annual multi-day auto-culture event in March at Finley Stadium /
    First Horizon Pavilion (https://www.riversidechattanooga.com/).
  - **World of Wheels Chattanooga** — annual indoor show in January at the Chattanooga Convention
    Center; 2026 edition was Jan 9–11 (https://worldofwheels.net/chattanooga/).
- Register the source in `build_sources()` behind a new `events_fixtures_enabled` setting
  (default true — the source is pure code, needs no network or credentials).
- Recurrence expansion is a pure function (rule + horizon → occurrences), unit-tested offline.
- **Spec adjustment**: the events spec's pluggable-source requirement currently forbids any
  "sample/fixture source" importable by the application. That prohibition targets fake demo data;
  it is narrowed so curated registries of *real* events remain first-class while sample/demo data
  stays banned. It also loosens "no sources are active by default" to "no *network* sources".
- Honest caveat recorded as a requirement: this is manual curation and can drift when organizers
  change dates. Mitigations: every fixture's `source_url` points at the organizer's page, and
  fixtures are reviewed when their rules expire (annual entries carry explicit dates that need
  yearly review).

## Capabilities

### New Capabilities

None — this extends the existing `events` capability with another source, exactly the "new source
class plus registration" path the spec already promises.

### Modified Capabilities

- `events`: (1) ADDED requirement for the local fixtures source — code-as-config registry,
  bounded-horizon recurrence expansion, `events_fixtures_enabled` gate, organizer `source_url` on
  every emitted event, stable `source_event_id` per occurrence so repeat ingests dedup cleanly;
  (2) MODIFIED "Pluggable event source interface" requirement — narrow the fixture prohibition to
  sample/demo data (curated real-event registries are allowed) and scope "no sources active by
  default" to network sources.

## Impact

- **New code**: `app/events/sources/fixtures.py` (source class + `FIXTURES` registry data +
  pure recurrence expansion).
- **Modified code**: `app/events/sources/__init__.py` (`build_sources()` registration),
  `app/config.py` (`events_fixtures_enabled: bool = True`), `pyproject.toml` (promote
  `python-dateutil` from transitive dep — already installed via icalendar — to a direct
  dependency, since `dateutil.rrule` drives recurrence expansion).
- **Tests**: new offline unit tests for recurrence expansion and registry validity; existing
  ingest/dedup/tagging/geocoding pipeline is untouched.
- **No changes** to ingest, storage, migrations, API, or frontend — the whole point of the
  pluggable source interface. No new network calls (geocoding of the fixture addresses goes
  through the existing Nominatim + cache path).
