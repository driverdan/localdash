## Context

The news registry (`app/news/registry.py`, `SOURCES`) is the code source of truth for news
outlets; `sync_registry()` upserts it at startup. Adding an outlet is a data-only edit to that
list — no schema or code-path changes. The Pulse (chattanoogapulse.com) runs on Metro Publisher
(not WordPress) and exposes a single global RSS feed at `/api/rss/content.rss` — a valid RSS 2.0
feed (~30 current items, includes `media:content` images the recently-added feed-image support
consumes). It has no per-item `<category>` tags and no working section-scoped feeds.

## Goals / Non-Goals

**Goals:**
- Surface The Pulse's local arts, food, music, and culture coverage on the news homepage.
- Fit the existing registry pattern with no new code or migration.

**Non-Goals:**
- Per-section categorization of this outlet's articles.
- Any change to fetching, clustering, storage, or API behavior.

## Decisions

**Use the single global feed, mapped to `life`.**
Metro Publisher exposes only the one global feed (`/api/rss/content.rss`); its `?section=` query
parameter is silently ignored (returns the identical global feed), so per-section feeds are not
available. Because the app assigns category per feed (feed items carry no `<category>` tags it
reads), a single feed means all articles land under one category. `life` is the correct bucket:
The Pulse is an arts & entertainment / food / culture weekly, matching how the app's `life`
category is already used for lifestyle coverage.

- *Alternative considered: map to `news`* (as the general-news Chronicle outlet was). Rejected:
  The Pulse is not a general-news outlet; routing its concert previews and restaurant features
  into the primary `news` cluster would dilute local hard-news coverage. Its arts identity fits
  `life`.

**Reuse the registry's existing browser User-Agent.**
No per-source UA handling is needed; the Metro Publisher feed serves the standard registry
browser UA without rate-limiting.

## Risks / Trade-offs

- [Feed mixes lighter local news (e.g. gas prices, blood drives) in with arts coverage under
  `life`] → Accepted; category is per-feed and the outlet's identity is arts/culture, so `life`
  is the best single bucket. Out of scope to re-categorize per item.
- [The Pulse's arts coverage rarely clusters with other outlets] → Expected, not a problem: it is
  the only local arts voice, so its stories appear as standalone cards under `life`, which is the
  intended behavior.
- [Metro Publisher later adds working section feeds] → Not addressed now; a future change can add
  section feeds if they become available and useful.
