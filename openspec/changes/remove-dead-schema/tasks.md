## 1. Migration

- [ ] 1.1 Add `alembic/versions/0010_remove_dead_source_columns.py` (`down_revision = "0009"`; if another migration has taken `0010` by then, use the next free number), with a docstring explaining why the columns go: `upgrade()` runs `ALTER TABLE sources DROP COLUMN config` and `ALTER TABLE sources DROP COLUMN enabled`
- [ ] 1.2 `downgrade()` re-adds `enabled BOOLEAN NOT NULL DEFAULT TRUE` and `config JSONB NOT NULL DEFAULT '{}'::jsonb` (the `0001` definitions), with a comment that this loses nothing because every row held those defaults

## 2. Source columns

- [ ] 2.1 In `app/models.py`, remove `Source.enabled` and `Source.config` (keep `poll_interval_seconds`)
- [ ] 2.2 In `app/scheduler.py` `_record_run`, remove `enabled=True` from the insert values
- [ ] 2.3 In `app/api/timeseries.py` `list_sources`, add a `request: Request` parameter and report `"enabled": r.key in request.app.state.collectors`; keep every other response key and its order unchanged; add a short docstring saying `enabled` means "a collector for this key is registered in the running app"

## 3. Relationships

- [ ] 3.1 In `app/models.py`, remove `Entity.observations` and `Observation.entity`, and the now-unused `relationship` import
- [ ] 3.2 In `app/news/models.py`, remove `NewsSource.feeds` and `NewsFeed.source`, and the now-unused `relationship` import
- [ ] 3.3 In `app/events/models.py`, remove `Tag.events` and change `Event.tags` to `relationship(secondary=event_tags)` with no `back_populates`; leave `Event.links` / `EventLink.event` as they are
- [ ] 3.4 Grep `app/` and `tests/` once more for `.observations`, `.entity`, `.feeds`, `.source` (on news feed objects), and `.events` (on tag objects) to confirm nothing reads the removed attributes

## 4. Tests

- [ ] 4.1 DB test (`tests/test_api_timeseries.py`): seed two `sources` rows, call `list_sources` with a stand-in request whose `app.state.collectors` contains only the first key, and assert the exact response: both rows listed, `enabled` is `true` for the first and `false` for the second, and the key set is exactly `key, name, enabled, poll_interval_seconds, last_run_at, last_status, last_error, last_count`
- [ ] 4.2 DB test: call `_record_run` twice for a fake collector (the first inserts, the second updates through the conflict path) and assert the stored `name`, `poll_interval_seconds`, `last_status`, `last_error`, and `last_count` reflect the second call
- [ ] 4.3 DB test: query `information_schema.columns` for `sources` on the migrated test database and assert it has no `config` or `enabled` column
- [ ] 4.4 Run the existing events ingest and API tests unchanged, to confirm tag assignment, event merging (`session.delete` of the losing event), and `purge_blocked_tags` still work with the one-way `Event.tags`
- [ ] 4.5 Run the existing news DB tests unchanged, to confirm the registry sync (which deletes feeds and outlets with Core statements) still works without `NewsSource.feeds` / `NewsFeed.source`

## 5. Docs

- [ ] 5.1 `AGENTS.md`, "Source-agnostic data model": describe `sources` as one row per source that has run, holding its name, poll interval, and last-run telemetry (written by `_record_run`), and say that whether a collector runs is decided by the `*_enabled` settings in `build_collectors()`, never by a stored flag
- [ ] 5.2 `AGENTS.md`, "API / frontend conventions" timeseries routes bullet: note that `/sources` lists every source that has recorded a run and that its `enabled` reports whether that source's collector is registered in the running app
- [ ] 5.3 Update the `app/models.py` module docstring's `sources` line if it still implies a stored registry or config

## 6. Verify

- [ ] 6.1 Run the full backend suite and the lint/format checks; all pass
- [ ] 6.2 Against a scratch database: `alembic upgrade head`, `alembic downgrade 0009`, `alembic upgrade head` all succeed; if PR #269 has landed, also run `alembic check` after the final upgrade and confirm no drift
- [ ] 6.3 Rebuild and restart via Docker (`sg docker -c 'docker compose up --build -d'`), confirm the migration applied (`\d sources` shows no `config`/`enabled`), and confirm `GET /api/v1/timeseries/sources` returns every source with `enabled: true` for the running collectors
