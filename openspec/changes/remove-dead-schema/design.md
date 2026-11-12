## Context

A grep of `app/`, `tests/`, `alembic/`, and `frontend/src/` on current `main` shows five
relationship attributes with no reader:

- `Entity.observations` and `Observation.entity` (`app/models.py`)
- `NewsSource.feeds` and `NewsFeed.source` (`app/news/models.py`)
- `Tag.events` (`app/events/models.py`)

No code accesses them, passes them to `selectinload`/`joinedload`, or uses them as constructor
keywords. Every delete that touches these tables is a Core `delete()` statement
(`purge_blocked_tags`, the news registry sync) that relies on the database's `ON DELETE CASCADE`,
not on ORM cascades. The one ORM `session.delete()` (merging a duplicate event in
`app/events/ingest.py`) deletes an `Event`, whose `tags` and `links` relationships stay.

Migration `0001` also created `sources` with `enabled BOOLEAN NOT NULL DEFAULT TRUE` and
`config JSONB NOT NULL DEFAULT '{}'`. Today they are dormant:

- `Source.config` has no reader or writer outside migration `0001`.
- `Source.enabled` is written only by `_record_run` as the literal `True` on insert, and is not
  in the upsert's `set_` clause. Its only reader is `list_sources` (`app/api/timeseries.py`),
  which echoes it.
- Which collectors run is decided by `build_collectors()` in `app/collectors/__init__.py`, from
  the `hc911_enabled` / `tdot_enabled` / `epb_enabled` / `tnaw_enabled` settings.

The first version of this change dropped both columns for that reason. In review on PR #330 the
repo owner said that configuration will soon move from files into the database, and that existing
fields that work will use, such as `sources.enabled`, should be kept. `sources.config` is the
per-source configuration field of the same table, so the same reasoning covers it.

Not dead, and left alone as before: `Source.poll_interval_seconds` (written by `_record_run`,
served by `/sources`), `NewsSource.enabled` (registry-synced; the news fetcher and
`/news/sources` filter on it), `Event.tags`, `Event.links`, and `EventLink.event`.

## Goals / Non-Goals

**Goals:**

- ORM models declare only relationships that some code uses.
- `sources.enabled` and `sources.config` are kept, and the code and `AGENTS.md` say why, so they
  are not mistaken for dead schema again.

**Non-Goals:**

- Designing or building database-backed configuration. That is its own change. This one only
  avoids removing the fields it will use.
- Changing what `GET /api/v1/timeseries/sources` reports for `enabled`. It keeps echoing the
  stored value. See the decision below.
- Any migration or schema change.
- Adding a Pydantic response model for `/sources`. That belongs to `add-typed-contracts`.
- Any other model/migration alignment (index names, `spatial_index`, etc.). That is PR #269.

## Decisions

**Keep `sources.enabled` and `sources.config`, and mark them as reserved.** The columns stay in
the schema and on `Source` exactly as they are. A comment above them in `app/models.py`, and one
sentence in the `AGENTS.md` data-model section, say that they are reserved for the planned move
of configuration into the database, and that until then the `*_enabled` settings in
`build_collectors()` decide which collectors run. Alternative considered: keep the columns and
say nothing. Rejected, because the original review flagged them as dead on good evidence, and the
next reader will reach the same conclusion unless the intent is written down where they look.

**Leave `/sources` and `_record_run` alone.** The first version derived the response's `enabled`
from the collectors registered in the running app, because a stored constant is wrong for the
leftover row of a collector that has since been disabled. That inaccuracy is real, but the fix
would be undone as soon as the stored flag becomes the source of truth, which is the direction
configuration is taking. Changing the meaning of the key twice is worse than leaving it as is
for now. The frontend never calls this endpoint, so nothing visible depends on it meanwhile.
Alternative considered: have startup write `enabled = false` for rows whose collector is not
registered. Rejected: it decides how the database flag and the settings relate, which is exactly
what the configuration change has to design.

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

These are not "fields that will be used for configuration": they are Python attributes with no
column behind them, and none of them carries configuration. Database-backed configuration can
re-declare any relationship it turns out to need.

**`Event.tags` becomes a one-way relationship.** `Tag.events` is the `back_populates` partner of
`Event.tags`, so the implementation declares `Event.tags` as
`relationship(secondary=event_tags)` with no `back_populates`. Appending tags to `event.tags` in
ingest keeps working; the only behavior lost is the in-memory backref bookkeeping on the `Tag`
side, which nothing reads. Deleting an `Event` through the ORM still clears its `event_tags` rows
through `Event.tags`. Deleting a `Tag` happens only through Core `delete()`, where the database's
`ON DELETE CASCADE` on `event_tags.tag_id` removes the links.

**The change keeps its name.** `remove-dead-schema` no longer drops schema, but the merged
sibling proposals refer to it by this name, and renaming it would leave those references
pointing at nothing.

## Risks / Trade-offs

- [`/sources` keeps reporting `enabled: true` for the leftover row of a disabled collector] →
  Accepted until database-backed configuration gives the flag a real meaning. Nothing in the
  repo reads the endpoint's `enabled`.
- [Someone wants a relationship back] → Re-declare it. No schema change is needed.
- [The "reserved" note goes stale if the configuration work changes direction] → It is one
  comment and one sentence, and the change that settles the design updates both.

## Migration Plan

None. There is no schema change. Rollback is a plain revert.

## Interaction with other changes

**PR #269 (`fix-alembic-schema-drift`, open, last updated 2026-10-14).** It makes `alembic check`
pass by fixing model declarations, imports the news and events models in `alembic/env.py`,
filters extension-owned objects, and adds `alembic check` to CI.

- *Semantics:* compatible in either order. Relationships are not schema, so `alembic check`
  ignores their removal, and this change no longer touches any column.
- *Text:* both touch `app/models.py` and `app/events/models.py`, so whichever lands second will
  have small rebase conflicts. #269's last `app/models.py` hunk uses the
  `entity: Mapped["Entity"] = relationship(back_populates="observations")` line as context, and
  this change deletes it. Its `app/events/models.py` hunks sit just above the `Event.tags` line
  that this change edits.

**Sibling proposals from the same architecture review.** Without the column drop, this change no
longer has an ordering constraint. It can land at any point.

- `extract-orm-base` relocates `Base` to `app/orm.py`. It edits the top of `app/models.py`; this
  change edits the `Source` comment, two relationship lines and the import line. Any conflict is
  in the import block and is trivial.
- `unify-refresh-orchestration` moves `_record_run`. This change no longer touches it.
- `add-typed-contracts` adds a `SourceStatus` response model that includes `enabled: bool`. Its
  notes say this change "may drop" or "owns removing" `enabled`. That no longer applies: the key
  and the column both stay, and that model needs no follow-up.
- `tighten-python-tooling` enforces unused-import rules. The `relationship` imports in
  `app/models.py` and `app/news/models.py` become unused here and are removed in this change.
- `relax-backend-feature-separation` and several other siblings edit `AGENTS.md`. This change
  edits one bullet in the data-model section.

## Open Questions

- Is `sources.config` one of the fields the configuration work will use? This design assumes
  yes, since it is the per-source configuration column next to `enabled`. If not, dropping it is
  a small follow-up migration.
