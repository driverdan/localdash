## Why

Several ORM models declare relationships that no code reads. They suggest data access paths
that do not exist and, under the async session, would raise on first lazy access. Removing them
leaves the models describing how the code really navigates.

The first version of this change also dropped `sources.config` and `sources.enabled`, because
nothing reads or changes them today. That part is withdrawn. Configuration is going to move from
files into the database, and these columns are the fields that work will use. They stay, and this
change records why, so a later review does not propose removing them again.

## What Changes

- Remove the unread ORM relationships `Entity.observations` / `Observation.entity`,
  `NewsSource.feeds` / `NewsFeed.source`, and `Tag.events`. `Event.tags` stays (ingest and the API
  use it) but no longer declares `back_populates`. `Event.links` / `EventLink.event` stay. All
  foreign keys and their `ON DELETE CASCADE` rules are unchanged; these are Python-side
  attributes only.
- Keep `sources.enabled` and `sources.config`, in the schema and on the `Source` model. Mark them
  in `app/models.py` and `AGENTS.md` as reserved for the planned database-backed configuration,
  and say that until then the `*_enabled` settings in `build_collectors()` decide which
  collectors run.
- No migration, no change to `_record_run`, and no change to `GET /api/v1/timeseries/sources`,
  which keeps returning the stored `enabled` value.
- Kept, as before: `Source.poll_interval_seconds` (served by `/sources`) and `NewsSource.enabled`
  (filters which outlets the news fetcher runs).

The change keeps the name `remove-dead-schema` although it no longer drops any schema, because
the sibling proposals already merged refer to it by that name.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `project-documentation`: `AGENTS.md` identifies `sources.enabled` and `sources.config` as
  reserved configuration columns and says what decides which collectors run today.

## Impact

- `app/models.py`: drop `Entity.observations`, `Observation.entity`, and the now-unused
  `relationship` import; add a comment on `Source.enabled` / `Source.config`; update the module
  docstring's `sources` line.
- `app/news/models.py`: drop `NewsSource.feeds`, `NewsFeed.source`, and the now-unused
  `relationship` import.
- `app/events/models.py`: drop `Tag.events`; `Event.tags` loses `back_populates`.
- `AGENTS.md`: the data-model note.
- No schema change, no migration, no API change, no frontend change, no new dependencies.
