## Why

Outlets sometimes publish feed items with a `pubDate` in the future, and the fetcher stores it
as-is. Stories are sorted by their latest published time and the frontend's `timeAgo` floors at
zero, so a future-dated article sits at the top of the news list showing "0m ago" until its date
passes. It also stays inside the 72-hour window for that whole time. Chattanoogan.com does this
regularly: a "Mocs / Vols Basketball TV Schedules" item dated Nov 28 was first fetched Oct 28,
which pins it for 30 days. The production DB has 25 such rows, 1 to 41 hours ahead plus the
30-day one. The Times Free Press has done it at least once, so this is not specific to one source.

## What Changes

- At ingest, an article's stored `published` time is capped at its fetch time:
  `published = min(feed_date, fetched_at)`. An article cannot have been published after we first
  saw it. This applies to every source and to both the RSS and HTML-scrape fetch paths, with no
  tolerance window.
- The spec now states that `published` is set when the row is first inserted and is not changed
  by later re-fetches. The upsert already behaves this way. Making it explicit guarantees that a
  capped item will not jump back to the top when its claimed date arrives.
- A one-time data migration sets `published = fetched_at` on existing rows where
  `published > fetched_at`, so articles that are already stuck move to their correct place.
  It cannot be reversed: the original feed dates are not kept.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `news`: the "Article storage and deduplication" requirement gains the published-time cap, the
  rule that `published` never changes after insert, and scenarios for a future-dated item and a
  re-fetch of a capped item.

## Impact

- `app/news/fetcher.py`: apply the cap where article rows are written (`upsert_articles`). That
  is the one place both fetch paths go through.
- `alembic/versions/0009_*`: a new data-only migration that backfills existing future-dated rows.
- `tests/`: unit and DB tests for the cap and for the no-re-bump behavior.
- Nothing else changes. Story sorting, the stories-window cutoff, the clustering time windows,
  and the frontend `timeAgo` are all fixed without edits because they read the corrected
  `published` value. No API shape changes and no new dependencies.
