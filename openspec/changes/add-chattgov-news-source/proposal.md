## Why

The City of Chattanooga's official "Latest News" page
(https://chattanooga.gov/stay-informed/latest-news) publishes primary-source municipal
announcements — police incidents, road closures, city initiatives — that none of the seven
aggregated outlets carry firsthand. It is a high-value civic feed, but unlike every existing news
source it exposes **no usable RSS feed**: the site's only RSS (`/rss.xml`) is the Drupal frontpage
feed, which contains calendar events and zero news, and its JSON:API is disabled. The content is
only available as a server-rendered Drupal View (HTML). Adding it therefore requires the news
pipeline to gain a second, non-RSS ingestion path.

## What Changes

- Register a new news source, `chattgov` ("City of Chattanooga"), under the `news` category,
  pointing at the Latest News listing page.
- Introduce a per-feed **kind** in the code registry: `rss` (default, all existing feeds) vs
  `html` (scraped). Kind is a registry-level attribute resolved by a lookup helper (mirroring the
  existing `use_feed_tags` / `uses_feed_tags` pattern) — **no database schema change**.
- Branch the fetch path on kind: `rss` feeds keep the existing `feedparser` flow unchanged; `html`
  feeds are fetched with `httpx` and parsed from the listing HTML with BeautifulSoup (the same
  stack the events scrapers already use). One `.views-row` becomes one article: title + absolute
  URL (`.views-field-title h3 a`), published datetime (`.views-field-created time[datetime]`, tz
  offset → UTC), and summary (`.views-field-body .field-content`). `guid` = the article URL;
  `image_url` = null (the listing carries no image and no article page is fetched).
- Reuse the existing storage, dedup, categorization, clustering, and telemetry paths verbatim:
  per-feed error isolation, browser User-Agent, `(source_id, guid)` upsert, and content
  categorization (`classify()` with no feed tags → keyword match → `news` fallback).

## Capabilities

### New Capabilities
<!-- None. This extends the existing news pipeline. -->

### Modified Capabilities
- `news`: the source/feed registry gains a per-feed `kind` (`rss` | `html`) and an eighth outlet;
  scheduled fetching gains an HTML-scrape path alongside the RSS path, both preserving per-feed
  error isolation and the browser User-Agent; article storage covers HTML-scraped articles
  (`image_url` always null, `guid` = URL).

## Impact

- **Code**: `app/news/registry.py` (new `chattgov` source + `kind` field + `feed_kind()` helper),
  `app/news/fetcher.py` (branch RSS vs HTML fetch/parse). No new dependencies — `httpx` and
  `beautifulsoup4` are already project dependencies used by the events scrapers.
- **Database**: none. `news_feeds`/`news_articles` schemas are unchanged; `kind` lives only in the
  code registry, and HTML articles reuse the existing columns (`image_url` nullable).
- **Behavior**: an eighth source appears in the News section and the sources-health footer. The
  fetch cadence, clustering, and APIs are unchanged.
- **Risk**: HTML scraping is brittle to markup changes on chattanooga.gov (unlike a stable RSS
  contract). Mitigated by the existing per-feed error isolation — a parse failure records on
  `last_status` and never aborts the cycle.
