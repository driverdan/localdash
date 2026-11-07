## Context

`fetcher.py` turns each feed item's date into `published`: `_entry_published` for RSS, and
`_row_published` for the HTML scrape. It uses whatever the feed says and only falls back to
`now` when the date is missing. Both paths build rows that include `fetched_at = now` and pass
them to `upsert_articles`. On a `(source_id, guid)` conflict, that function updates only
`category`. As a result, `published` and `fetched_at` are written once, on first insert, and
`fetched_at` effectively means "first seen".

Everything downstream reads `published`:

- `stories.get_stories`: the window cutoff and the ascending sort.
- `build_stories`: `latest_published` sets the story order (descending).
- `clustering.py`: the corpus and window cutoffs, and the 36-hour story-window anchors.
- The frontend `timeAgo`: clamps negative ages to "0m ago".

A future-dated row therefore sorts first, stays in the window past its real age, and can anchor
or extend a cluster's time window incorrectly.

## Goals / Non-Goals

**Goals:**

- No stored article has `published` later than its `fetched_at`.
- Fix the value once at write time, so every reader is correct without changes.
- Correct the rows that are already stuck.

**Non-Goals:**

- Keeping the feed's claimed date. Nothing uses it.
- Detecting or showing "pinned" items separately.
- Filtering Chattanoogan's recurring boilerplate posts ("Get Emailed Headlines…", "Send Your
  Opinions…"). That is a separate problem.
- Re-reading `published` from later fetches. It stays fixed at insert.

## Decisions

**Cap at ingest, not at read time.** `published` is capped to `min(published, fetched_at)`
before the insert. Capping at read time (`LEAST(published, fetched_at)`) would keep the raw
value, but it would have to be repeated in the stories cutoff and sort, the clustering corpus,
window, and anchors, and the API output. Any new reader added later could miss it. Capping at
ingest fixes one value that every reader trusts. Storing a separate `published_raw` column was
also rejected, because no code would read it.

**Apply the cap inside `upsert_articles`.** RSS and HTML rows both go through
`upsert_articles`, and each row already carries its own `fetched_at`. Capping each row there
(`row["published"] = min(row["published"], row["fetched_at"])`) enforces the rule once, in the
function that writes the rows, so a new fetch path cannot skip it. The parsers
(`_entry_published`, `_row_published`, `parse_html_listing`) keep returning the feed's date, so
their existing tests still describe parsing only. Capping in the parsers would mean two call
sites and an extra `now` argument. Because `fetched_at` is the same `now` the row was built with,
capping against `fetched_at` is the same as capping against "now" at insert. On a conflict the
capped value is discarded anyway, because the update set does not include `published`.

**Cap strictly, with no tolerance window.** An item dated a few minutes ahead gets its fetch time,
at most one poll interval (15 minutes by default) earlier than its claimed time. A tolerance would
only let small skews show "0m ago" briefly, which is the symptom being fixed.

**Apply to all sources.** The Times Free Press has also produced a future-dated item. The rule
"published ≤ first seen" holds for every outlet, so there is no per-source registry flag.

**`published` is fixed at first insert.** This is current behavior: the upsert's update set is
`{category}` only. The spec will now state it, because the fix depends on it. If later fetches
could rewrite `published`, a capped 30-day item could be rewritten to its real future date and
pinned again. A test will cover it.

**Backfill with an Alembic data migration.** `0009_clamp_future_article_dates` runs
`UPDATE news_articles SET published = fetched_at WHERE published > fetched_at`. This follows the
data-update pattern in `0004_geocode_retry`. `downgrade()` does nothing, because the original
dates are gone and restoring them would re-create the bug. Clusters do not need to be rebuilt in
the migration: the app reclusters after the fetch it runs at startup, which picks up the
corrected times.

## Risks / Trade-offs

- **[Risk] A feed's clock runs slightly fast, so every new item gets `fetched_at` instead of its
  own time.** → Accuracy then depends on the poll interval (15 minutes or less). Order between
  sources stays roughly correct, and ordering inside one fetch batch collapses to a tie. This is
  acceptable compared with items stuck at the top.
- **[Risk] A future-dated item that is deliberately pinned (for example a TV schedule) now
  appears once and ages out after 72 hours, even though the outlet keeps it in the feed for weeks.**
  → This is intended. The digest is about recent news, not the outlet's pins.
- **[Trade-off] The feed's original future date is lost, so there is nothing to debug from
  later.** → The DB check that found the problem used `published > fetched_at`. After this change
  that query always returns zero rows, so it can no longer be used to find future-dated items.
  Accepted, since nothing else reads the original date.
- **[Risk] Backfill affects the wrong rows.** → The `WHERE published > fetched_at` predicate
  only matches rows that broke the rule. Valid rows are never touched. The update is idempotent.

## Migration Plan

1. Deploy: the container entrypoint runs `alembic upgrade head`, which applies the backfill, then
   the app starts and its startup fetch reclusters everything.
2. Rollback: revert the code. The backfilled rows stay capped, which is harmless.
   `downgrade()` is a no-op.
