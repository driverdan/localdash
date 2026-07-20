## 1. Config

- [x] 1.1 Add `events_blocked_tags: str = ""` to `Settings` in `app/config.py` with a comment noting comma-separated, lowercased names
- [x] 1.2 Add a shared normalization helper that returns the effective blocklist as a `set[str]` (split on commas, strip whitespace, lowercase, drop empties) — a `blocked_tags` property on `Settings` or a small function reused by ingest and startup

## 2. Ingest prevention

- [x] 2.1 In `app/events/ingest.py`, after `names` is computed (both the keyword-derived and source-supplied branches), subtract the effective blocklist set before the `_get_or_create_tag` loop so blocked tags are never created or attached
- [x] 2.2 Confirm the blocklist is read via the shared helper (not re-parsed inline)

## 3. Startup purge

- [x] 3.1 In the `lifespan` handler in `app/main.py`, within the existing `SessionLocal()` block, execute `DELETE FROM tags WHERE name IN (:blocked)` when the effective blocklist is non-empty (rely on the `event_tags` ON DELETE CASCADE to drop associations)
- [x] 3.2 Guard against an empty blocklist so no delete runs when `events_blocked_tags` is unset

## 4. Tests

- [x] 4.1 In `tests/test_events_ingest.py`, add a test that ingesting with a blocked keyword topic strips it from a keyword-derived event (e.g. block `food`, ingest "Live music and food trucks" → tagged `music` only)
- [x] 4.2 Add a test that a blocked source-supplied tag is stripped (source reports `["Nightlife","Music"]` with `nightlife` blocked → tagged `music` only)
- [x] 4.3 Add a startup-purge test that a pre-existing blocked tag and its event associations are deleted, and that an empty blocklist is a no-op
- [x] 4.4 Add a normalization test (` Politics , , MUSIC ` → `{politics, music}`)

## 5. Verify

- [x] 5.1 Run the events test suite (`pytest tests/test_events_ingest.py tests/test_events_tagging.py tests/test_api_events.py`) and the linters
- [x] 5.2 Rebuild Docker (`docker compose up --build`) and confirm a configured `EVENTS_BLOCKED_TAGS` value purges on startup and keeps the tag off newly ingested events
