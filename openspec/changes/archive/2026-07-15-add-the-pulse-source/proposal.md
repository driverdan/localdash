## Why

The news aggregator currently covers five Chattanooga outlets, all general-news or
broadcast sources. The Pulse (chattanoogapulse.com) is Chattanooga's long-running arts &
entertainment weekly, so the homepage has no coverage of local music, food, and cultural
happenings that no other registered outlet provides.

## What Changes

- Add The Pulse to the news source registry as a sixth outlet.
- Register a single feed: the site's global RSS feed
  (`https://www.chattanoogapulse.com/api/rss/content.rss`), mapped to the `life` category.
  Section feeds are intentionally NOT used — The Pulse runs on Metro Publisher, which exposes
  only this one global feed (its `?section=` query parameter is silently ignored), and feed
  items carry no per-item category tags the app reads, so all of this outlet's articles land
  under `life`.
- No schema change and no new code: `sync_registry()` upserts the new entry into the database
  at application startup.

## Capabilities

### New Capabilities
<!-- None; this extends the existing news capability. -->

### Modified Capabilities
- `news`: The "News source and feed registry" requirement enumerates the outlets covered.
  It changes from five outlets to six, adding The Pulse.

## Impact

- Code: `app/news/registry.py` (`SOURCES` list) — one new source entry.
- Data: at next startup, `sync_registry()` inserts the new source and feed rows; the scheduled
  refresh then begins fetching the feed. No migration.
- No API, dependency, or configuration changes.
