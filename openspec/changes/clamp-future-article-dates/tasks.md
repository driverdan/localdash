## 1. Cap published at ingest

- [x] 1.1 In `app/news/fetcher.py` `upsert_articles`, cap each row's `published` at its own `fetched_at` (`min(published, fetched_at)`) before building the insert, with a comment explaining why (outlets future-date items; published ≤ first seen)
- [x] 1.2 Confirm the conflict update set stays `{category}` only (published/fetched_at fixed at first insert) and note that invariant in the `upsert_articles` docstring
- [x] 1.3 Update the `fetcher.py` module docstring's list of hard-won feed behaviors to include the future-date cap

## 2. Backfill existing rows

- [x] 2.1 Add `alembic/versions/0009_clamp_future_article_dates.py` (down_revision `0008`) whose `upgrade()` runs `UPDATE news_articles SET published = fetched_at WHERE published > fetched_at`, with the statement held in a module-level constant so tests can reuse it
- [x] 2.2 Make `downgrade()` a documented no-op (original feed dates are not retained; restoring them would reintroduce the bug)

## 3. Tests

- [x] 3.1 DB test (`tests/test_news_db.py`): upserting a row with `published` in the future stores `published == fetched_at`
- [x] 3.2 DB test: upserting a row with `published` in the past stores the feed date unchanged
- [x] 3.3 DB test: re-upserting a capped article with its original future `published` (and a later `fetched_at`) leaves the stored `published` and `fetched_at` unchanged
- [x] 3.4 DB test: seed violating and non-violating rows directly, execute the migration's backfill statement (loaded from the `0009` module), and assert only the violating rows changed, to `published = fetched_at`
- [x] 3.5 DB test: `get_stories` orders a capped future-dated article by its fetch time, not at the top ahead of newer articles

## 4. Verify

- [x] 4.1 Run the backend test suite and lint/format checks; all pass
- [x] 4.2 Rebuild and restart via Docker (`sg docker -c 'docker compose up --build -d'`), confirm the migration applied, and confirm `SELECT count(*) FROM news_articles WHERE published > fetched_at` returns 0
- [x] 4.3 Check the live news list: the Chattanoogan "Mocs / Vols Basketball TV Schedules" item is no longer pinned at the top
