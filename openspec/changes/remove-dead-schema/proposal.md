## Why

The timeseries `sources` table carries two columns that nothing uses, and several ORM models
declare relationships that no code reads. `sources.config` (JSONB) is never read or written.
`sources.enabled` is always inserted as `true` and never updated, so `GET
/api/v1/timeseries/sources` reports `enabled: true` even for a source whose collector has since
been turned off with its `*_enabled` setting. Whether a collector runs is decided only by
`build_collectors()` in `app/collectors/__init__.py`. The unused relationships suggest data access
paths that do not exist and, under the async session, would raise on first lazy access. Removing
all of this leaves the models describing only what the code does.

## What Changes

- Drop `sources.config` and `sources.enabled` from the schema with a new hand-written migration
  (`0010` on current `main`), whose downgrade re-adds both columns with their original types,
  `NOT NULL` constraints, and defaults. Remove both mapped columns from `Source`.
- Stop inserting `enabled=True` in `_record_run` (`app/scheduler.py`).
- Keep the `enabled` key in the `GET /api/v1/timeseries/sources` response, but derive it from
  the running app: `true` when a collector with that key is registered in `app.state.collectors`
  (the collectors built from the `*_enabled` settings), `false` otherwise. The response shape is
  unchanged. **Observable change:** a source row left over from a collector that has since been
  disabled now reports `enabled: false` instead of the stored, always-`true` value.
- Remove the unread ORM relationships `Entity.observations` / `Observation.entity`,
  `NewsSource.feeds` / `NewsFeed.source`, and `Tag.events`. `Event.tags` stays (ingest and the API
  use it) but no longer declares `back_populates`. `Event.links` / `EventLink.event` stay. All
  foreign keys and their `ON DELETE CASCADE` rules are unchanged; these are Python-side
  attributes only.
- Kept, deliberately: `Source.poll_interval_seconds` (served by `/sources`) and
  `NewsSource.enabled` (filters which outlets the news fetcher runs). Neither is dead.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `timeseries`: the "Source registry" requirement now says which rows are listed (every source
  that has recorded a run, including ones whose collector is no longer registered) and that
  `enabled` reports whether that source's collector is registered in the running app, rather
  than a stored flag.

## Impact

- `app/models.py`: drop `Source.enabled`, `Source.config`, `Entity.observations`,
  `Observation.entity`, and the now-unused `relationship` import.
- `app/news/models.py`: drop `NewsSource.feeds`, `NewsFeed.source`, and the now-unused
  `relationship` import.
- `app/events/models.py`: drop `Tag.events`; `Event.tags` loses `back_populates`.
- `app/scheduler.py`: `_record_run` no longer sets `enabled`.
- `app/api/timeseries.py`: `list_sources` takes the `Request` and derives `enabled`.
- `alembic/versions/0010_*`: new schema migration (two `DROP COLUMN`s; downgrade re-adds them).
- `tests/`: DB tests for the `/sources` response and `_record_run`; a check that the migrated
  `sources` table has no `config`/`enabled` columns.
- `AGENTS.md`: the data-model and timeseries-routes notes.
- No frontend change: the bundled frontend never calls `GET /api/v1/timeseries/sources`. No new
  dependencies.
