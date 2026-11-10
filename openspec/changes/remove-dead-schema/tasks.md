## 1. Relationships

- [ ] 1.1 In `app/models.py`, remove `Entity.observations` and `Observation.entity`, and the now-unused `relationship` import
- [ ] 1.2 In `app/news/models.py`, remove `NewsSource.feeds` and `NewsFeed.source`, and the now-unused `relationship` import
- [ ] 1.3 In `app/events/models.py`, remove `Tag.events` and change `Event.tags` to `relationship(secondary=event_tags)` with no `back_populates`; leave `Event.links` / `EventLink.event` as they are
- [ ] 1.4 Grep `app/` and `tests/` once more for `.observations`, `.entity`, `.feeds`, `.source` (on news feed objects), and `.events` (on tag objects) to confirm nothing reads the removed attributes

## 2. Reserved source columns

- [ ] 2.1 In `app/models.py`, leave `Source.enabled` and `Source.config` as they are and add a short comment above them: reserved for the planned database-backed configuration; nothing reads them to decide what runs yet; until then the `*_enabled` settings in `build_collectors()` decide
- [ ] 2.2 Update the `app/models.py` module docstring's `sources` line to match (one row per source that has run, its last-run status, and the reserved configuration columns)
- [ ] 2.3 Confirm the diff touches no migration, `_record_run`, or `list_sources`

## 3. Tests

- [ ] 3.1 Run the existing events ingest and API tests unchanged, to confirm tag assignment, event merging (`session.delete` of the losing event), and `purge_blocked_tags` still work with the one-way `Event.tags`
- [ ] 3.2 Run the existing news DB tests unchanged, to confirm the registry sync (which deletes feeds and outlets with Core statements) still works without `NewsSource.feeds` / `NewsFeed.source`
- [ ] 3.3 Run the existing timeseries ingest and API DB tests unchanged, to confirm nothing relied on `Entity.observations` / `Observation.entity`

## 4. Docs

- [ ] 4.1 `AGENTS.md`, "Source-agnostic data model": in the `sources` bullet, say that `enabled` and `config` are reserved for the planned database-backed configuration and are not unused schema to remove, and that until then the `*_enabled` settings in `build_collectors()` decide which collectors run

## 5. Verify

- [ ] 5.1 Run the full backend suite and the lint/format checks; all pass
- [ ] 5.2 If PR #269 has landed, run `alembic upgrade head && alembic check` against a scratch database and confirm no drift
- [ ] 5.3 Rebuild and restart via Docker (`sg docker -c 'docker compose up --build -d'`), confirm the app starts with no mapper configuration error, and confirm `GET /api/v1/timeseries/sources`, `GET /api/v1/news/stories` and `GET /api/v1/events/items` respond as before
- [ ] 5.4 `openspec validate remove-dead-schema --strict`
