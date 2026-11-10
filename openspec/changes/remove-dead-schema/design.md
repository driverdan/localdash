## Context

Migration `0001` created `sources` with `enabled BOOLEAN NOT NULL DEFAULT TRUE` and
`config JSONB NOT NULL DEFAULT '{}'`, presumably for a database-driven source registry. That
registry never happened: collectors are code-as-config in `app/collectors/__init__.py`, and
`build_collectors()` decides which run from the `hc911_enabled` / `tdot_enabled` / `epb_enabled`
/ `tnaw_enabled` settings. A grep of `app/`, `tests/`, `alembic/`, and `frontend/src/` on current
`main` confirms the review's findings:

- `Source.config` (`app/models.py:45`) has no reader or writer anywhere outside migration `0001`.
- `Source.enabled` (`app/models.py:43`) is written only by `_record_run`
  (`app/scheduler.py:108`) as the literal `True` on insert. It is not in the upsert's `set_`
  clause, so it can never change. Its only reader is `list_sources`
  (`app/api/timeseries.py:242`), which echoes it.
- `_record_run` runs only for registered collectors, so a collector that is later disabled stops
  updating its row, but the row stays, and `/sources` keeps reporting `enabled: true` for it.
- The frontend never calls `GET /api/v1/timeseries/sources`. `frontend/src/features/timeseries/`
  builds its source list from the static `SOURCES` table in `sources.ts`. The only `enabled`
  field the frontend reads is the news one (`features/news/types.ts`, from
  `/api/v1/news/sources`). No test calls `list_sources`.
- Relationships with no reader: `Entity.observations` (`app/models.py:83`),
  `Observation.entity` (`app/models.py:104`), `NewsSource.feeds` (`app/news/models.py:38`),
  `NewsFeed.source` (`app/news/models.py:56`), and `Tag.events` (`app/events/models.py:46`). No
  code accesses them, passes them to `selectinload`/`joinedload`, or uses them as constructor
  keywords. Every delete that touches these tables is a Core `delete()` statement
  (`purge_blocked_tags`, the news registry sync) that relies on the database's
  `ON DELETE CASCADE`, not on ORM cascades. The one ORM `session.delete()` (merging a duplicate
  event in `app/events/ingest.py`) deletes an `Event`, whose `tags` and `links` relationships
  stay.

Not dead, and left alone: `Source.poll_interval_seconds` (written by `_record_run`, served by
`/sources`), `NewsSource.enabled` (registry-synced; the news fetcher and `/news/sources` filter on
it), `Event.tags`, `Event.links`, and `EventLink.event`.

## Goals / Non-Goals

**Goals:**

- The `Source` model and `sources` table hold only columns the code reads or writes.
- `/sources` reports a truthful `enabled` without a stored flag.
- ORM models declare only relationships that some code uses.

**Non-Goals:**

- A database-driven source registry or per-source runtime config. If one is wanted later, it
  needs its own design (who writes it, how it overrides settings) and its own migration; a
  dormant JSONB column does not get us there.
- Deleting `sources` rows for collectors that are no longer registered. Their last-run telemetry
  stays visible, now marked `enabled: false`.
- Adding a Pydantic response model for `/sources`. That belongs to `add-typed-contracts`.
- Any other model/migration alignment (index names, `spatial_index`, etc.). That is PR #269.

## Decisions

**Drop `sources.config`.** Nothing reads or writes it and nothing planned needs it. The proposed
sibling changes add no per-source DB config. Per-source settings already live in
`config.py` and the collector classes. Keeping a column "in case" costs a misleading line in the
model and a `{}` in every row. Alternative considered: keep it as a reserved extension point.
Rejected, because a future feature would have to design its semantics anyway, and adding a
JSONB column back is a one-line migration.

**Drop `sources.enabled`, but keep `enabled` in the `/sources` response, derived from the running
collectors.** `list_sources` gains a `request: Request` parameter and reports
`r.key in request.app.state.collectors`. This is the same registry `POST
/sources/{key}/refresh` already reads, and it is exactly the set built from the `*_enabled`
settings. Alternatives considered:

- *Keep the column and echo it (status quo).* Rejected: it is a stored constant that is wrong for
  every disabled collector's leftover row.
- *Keep the column and start writing it* (set `false` at startup for rows not in the collector
  set). Rejected: it duplicates in the database a fact the process already knows, and needs a
  startup write to keep it correct.
- *Drop `enabled` from the response.* This is the smallest change and nothing in the repo would
  break, since the frontend never calls this endpoint. Rejected because the spec documents the
  key, external tools or curl users may read it, and a truthful value is one line. It also keeps
  the response shape stable for the `/sources` response model that `add-typed-contracts` adds
  first (see below).

`app.state.collectors` is set in `main.py`'s lifespan. Offline route tests already set it to `{}`
(`tests/test_api_routes.py`); DB-backed handler tests call `list_sources` directly and pass a
minimal stand-in request carrying `app.state.collectors`.

**Remove the five unread relationship attributes.** They cost little at rest, but each is a trap.
Under `AsyncSession`, touching an unloaded relationship raises `MissingGreenlet`, so the
attributes look usable but are not. `Entity.observations` has no `passive_deletes`, so an ORM
`session.delete(entity)` would try to load every observation and null its `entity_id`, which is
part of the hypertable's primary key, and fail. Today nothing does that, because the database
cascade does the work. Removing the attributes makes the models match how the code really
navigates: by explicit `select()` with `where` on the FK column. The `ForeignKey` declarations
stay on the columns, so the schema, `alembic check`, and the DB cascades are unaffected.
Alternative considered: keep them as documentation. Rejected, because the `ForeignKey` on the
column already documents the link and a reader adding a real use can re-declare the pair in two
lines.

**`Event.tags` becomes a one-way relationship.** `Tag.events` is the `back_populates` partner of
`Event.tags`, so the implementation declares `Event.tags` as
`relationship(secondary=event_tags)` with no `back_populates`. Appending tags to `event.tags` in
ingest keeps working; the only behavior lost is the in-memory backref bookkeeping on the `Tag`
side, which nothing reads. Deleting an `Event` through the ORM still clears its `event_tags` rows
through `Event.tags`. Deleting a `Tag` happens only through Core `delete()`, where the database's
`ON DELETE CASCADE` on `event_tags.tag_id` removes the links.

**Migration `0010`, raw SQL like every other migration.** The number is the next free one on
current `main` (`0009` is the head). If another change adds a migration first, take the next
number and set `down_revision` to match.

```sql
-- upgrade
ALTER TABLE sources DROP COLUMN config;
ALTER TABLE sources DROP COLUMN enabled;

-- downgrade
ALTER TABLE sources ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE sources ADD COLUMN config JSONB NOT NULL DEFAULT '{}'::jsonb;
```

The downgrade restores the original column definitions from `0001`. It loses no information:
every existing row held `enabled = true` and `config = '{}'`, which are exactly the defaults the
re-added columns fill in. Column order differs after a downgrade (the columns move to the end of
the table). Nothing depends on column order, because every query names its columns.

## Risks / Trade-offs

- [An external client relied on `enabled` always being `true`] → It now goes `false` only for
  sources whose collector is not running, which is the case the flag was supposed to describe.
  The proposal calls this out as an observable change.
- [Old app code against the new schema during a deploy] → `select(Source)` and `_record_run` in
  the old code name `enabled` and `config`, so they would fail against a migrated table. The
  compose deploy runs migrations in the new container before it serves, and the old container is
  replaced in the same step, so there is no mixed window in practice. Rolling back the app means
  running the `0010` downgrade first.
- [Someone wants a relationship back] → Re-declare it. No schema change is needed.

## Migration Plan

1. Deploy normally (`docker compose up --build`): the app container runs `alembic upgrade head`,
   which applies `0010`, then serves.
2. `DROP COLUMN` on a table of a handful of rows is instant.
3. Rollback: `alembic downgrade 0009`, then deploy the previous image.

## Interaction with other changes

**PR #269 (`fix-alembic-schema-drift`, open, last updated 2026-10-14).** It makes `alembic check`
pass by fixing model declarations (explicit GIST `Index` entries with `spatial_index=False`, no
standalone `is_active` index, `ix_obs_source_time` with `DESC`), imports the news and events
models in `alembic/env.py`, filters extension-owned objects, and adds `alembic check` to CI. It
changes no schema and adds no migration.

- *Semantics:* compatible in either order. This change removes the two columns from both the
  model and the schema in the same change, so `alembic check` stays clean. Relationships are
  not schema, so `alembic check` ignores their removal. If #269 lands first, its CI step verifies
  this change's migration against the model, and the implementation should also run
  `alembic upgrade head && alembic check` locally. If this change lands first, #269 still needs
  no new migration.
- *Text:* both touch `app/models.py` and `app/events/models.py`, so whichever lands second will
  have small rebase conflicts. #269's last `app/models.py` hunk uses the
  `entity: Mapped["Entity"] = relationship(back_populates="observations")` line as context, and
  this change deletes it. Its `app/events/models.py` hunks sit just above the `Event.tags` line
  that this change edits. #269 is also stale against `main` (its `AGENTS.md` CI hunk predates the
  `isolate-test-database` rewrite), so it needs a rebase regardless.

**Sibling proposals from the same architecture review** (suggested landing order; this change is
12th):

- `extract-orm-base` (3, formerly `move-timeseries-into-package`) relocates `Base` to
  `app/orm.py` but no longer moves `app/models.py`. `Source`, `Entity`, and `Observation` stay in
  `app/models.py`, so the file paths in `tasks.md` hold; only the `Base` import there changes.
- `unify-refresh-orchestration` (4) moves `_record_run` out of `app/scheduler.py`. This change
  removes `enabled=True` from that function wherever it lives by then.
- `inject-settings-and-clock` (6) may change `_record_run`'s signature (injected `now`). That does
  not interact with dropping `enabled`.
- `add-typed-contracts` (8) adds a response model for `/sources` that will include `enabled:
  bool`. Keeping the key means that model's shape is unchanged; only how `list_sources` fills
  `enabled` changes. If `add-typed-contracts` builds the model with `from_attributes` from the ORM
  row, `enabled` must be passed explicitly once the column is gone.
- `tighten-python-tooling` (11) enforces unused-import rules. The `relationship` imports in
  `app/models.py` and `app/news/models.py` become unused here and are removed in this change.

No other sibling touches these columns or relationships.

## Open Questions

- Should `/sources` drop rows for collectors that are no longer registered instead of listing
  them with `enabled: false`? This design keeps them, because their last-run telemetry is still
  informative and deleting rows is a separate decision.
