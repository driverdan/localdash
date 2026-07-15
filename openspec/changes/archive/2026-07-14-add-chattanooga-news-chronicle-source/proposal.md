## Why

The news aggregator currently covers four Chattanooga outlets. Chattanooga News Chronicle
(chattnewschronicle.com) is an actively-published local outlet not yet represented, so its
local coverage is missing from the homepage.

## What Changes

- Add Chattanooga News Chronicle to the news source registry as a fifth outlet.
- Register a single feed: the site's primary WordPress feed
  (`https://www.chattnewschronicle.com/feed/`), mapped to the `news` category.
  Category feeds are intentionally NOT used — the primary feed is the actively-updated one,
  and because the app assigns category per feed (feed items carry no per-item category tags
  the app reads), all of this outlet's articles land under `news`.
- No schema change and no new code: `sync_registry()` upserts the new entry into the database
  at application startup.

## Capabilities

### New Capabilities
<!-- None; this extends the existing news capability. -->

### Modified Capabilities
- `news`: The "News source and feed registry" requirement enumerates the outlets covered.
  It changes from four outlets to five, adding Chattanooga News Chronicle.

## Impact

- Code: `app/news/registry.py` (`SOURCES` list) — one new source entry.
- Data: at next startup, `sync_registry()` inserts the new source and feed rows; the scheduled
  refresh then begins fetching the feed. No migration.
- No API, dependency, or configuration changes.
