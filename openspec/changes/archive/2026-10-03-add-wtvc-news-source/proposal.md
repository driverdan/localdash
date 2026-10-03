## Why

The news aggregator covers two of Chattanooga's broadcast newsrooms (WDEF News 12 and Local 3 /
WRCB) but not WTVC NewsChannel 9, the ABC affiliate. WTVC also runs the news for its Sinclair
sister station FOX Chattanooga. Without it, a major local TV newsroom never appears in the
cross-outlet story clusters.

## What Changes

- Add WTVC NewsChannel 9 (`newschannel9.com`) to the news source registry as a ninth outlet.
- Register a single feed: the Sinclair section feed `https://newschannel9.com/news/local.rss`,
  with category `news`. Content categorization then moves sports, politics and business stories
  out of `news` by keyword, as it does for the other single-feed outlets.
- Register the source with `use_feed_tags: False`: Sinclair tags every item with the same
  `<category>article</category>`, which describes the content type, not the topic.
- Do **not** add `foxchattanooga.com` as a separate outlet. It is the same WTVC newsroom: about
  90% of its `local.rss` items are identical to NewsChannel 9's. A second outlet would split every
  WTVC story into two near-identical source links and inflate `source_count`.
- No schema change and no new fetch path: the feed is standard RSS 2.0 handled by the existing
  `rss` kind, including its image `enclosure`s. `sync_registry()` upserts the entry at startup.

## Capabilities

### New Capabilities
<!-- None; this extends the existing news capability. -->

### Modified Capabilities
- `news`: the "News source and feed registry" requirement lists the covered outlets. It goes from
  eight outlets to nine by adding WTVC NewsChannel 9, and gains a scenario for that
  outlet's single tag-exempt `news` feed.

## Impact

- Code: `app/news/registry.py` (`SOURCES`), one new source entry; a registry test asserting the
  new source is tag-exempt.
- Data: at the next startup `sync_registry()` inserts the source and feed rows, and the scheduled
  refresh starts fetching the feed. No migration.
- No API, frontend, dependency or configuration changes.
