## Context

Every existing news source is an RSS feed. `app/news/fetcher.py` fetches each `NewsFeed` row with
`feedparser` (run in `asyncio.to_thread`), maps entries to article rows, and upserts on
`(source_id, guid)`. The registry (`app/news/registry.py`) is the source of truth: `SOURCES` is a
list of dicts upserted into `news_sources`/`news_feeds` at startup, and a `uses_feed_tags(slug)`
helper reads a per-source flag straight off `SOURCES` at fetch time rather than persisting it.

The City of Chattanooga's Latest News page has no usable RSS feed (its only RSS is the Drupal
frontpage/events feed; JSON:API is off). It is a server-rendered Drupal View. Each article is one
`div.views-row` containing:

- `div.views-field-created time[datetime]` — ISO-8601 timestamp with a `-04:00` offset
- `div.views-field-title h3 a` — headline text + relative href
  `/stay-informed/latest-news/<slug>`
- `div.views-field-body div.field-content` — a plain-text teaser

`httpx` and `beautifulsoup4` (stdlib `html.parser` backend) are already project dependencies, used
by the events scrapers (`app/events/sources/chattzoo.py`, `carcruisefinder.py`, `tribe.py`), which
establish the `async with httpx.AsyncClient(...)` + `BeautifulSoup(html, "html.parser")` pattern.

## Goals / Non-Goals

**Goals:**
- Ingest chattanooga.gov Latest News into the existing news pipeline (storage, dedup,
  categorization, clustering, APIs, telemetry all reused unchanged).
- Add a second ingestion transport (HTML scrape) with the smallest surface area, keeping the RSS
  path byte-for-byte unchanged.
- Keep the parse logic a pure, offline-testable function (matching `test_news_fetcher.py`).

**Non-Goals:**
- No database schema change and no Alembic migration.
- No fetching of individual article pages (no per-article images or full bodies).
- No general pluggable-scraper framework — exactly one `html` source, one parser.
- No frontend changes: the source surfaces through the existing sources footer and story list.

## Decisions

### 1. `kind` is a registry attribute resolved by lookup, not a DB column
Feeds gain an optional `"kind": "rss" | "html"` key in `SOURCES`, defaulting to `rss`. Rather than
adding a `kind` column to `news_feeds` (which would need a migration and a `sync_registry` change),
a `feed_kind(url) -> str` helper reads the kind off `SOURCES` by feed URL at fetch time — exactly
mirroring the existing `uses_feed_tags(slug)` helper. `fetch_all` already carries each feed's URL,
so the branch needs no new query. This keeps the change code-only and reversible by deleting the
source entry.

*Rejected:* a `news_feeds.kind` column — more moving parts (migration, model field, sync upsert)
for a value the registry already owns as source of truth.

### 2. Branch at `fetch_feed`, keep one storage path
`fetch_feed(session, feed, source_slug)` branches on `feed_kind(feed.url)`:
- `rss` → the current body (unchanged): `_parse_feed` + `feedparser` entry mapping.
- `html` → `_fetch_html(feed.url)` (async `httpx` GET with `USER_AGENT`, `follow_redirects=True`)
  → `parse_html_listing(html, base_url)` → the same `rows` shape fed to the existing
  `upsert_articles`.

Both branches build identical row dicts and share `upsert_articles`, so dedup, the
content-category recompute, clustering, and `last_fetch`/`last_status` telemetry in `fetch_all` are
untouched. Per-feed error isolation is already provided by the `try/except` around `fetch_feed` in
`fetch_all`; the html branch inherits it for free.

### 3. `parse_html_listing(html, base_url)` is a pure function
It returns a list of `{"url", "title", "summary", "published", "image_url": None, "guid": <url>}`
partial dicts (fetcher fills `source_id`, `category`, `fetched_at`), so it can be unit-tested
against a saved HTML fixture with no network or DB, matching `test_news_fetcher.py`. Per row:
- title/url from `.views-field-title h3 a` (`urljoin(base_url, href)` → absolute); a row missing
  either is skipped, mirroring the RSS loop's `if not url or not title: continue`.
- `published` from `.views-field-created time[datetime]` parsed with `datetime.fromisoformat`
  (handles the `-04:00` offset) and converted to UTC; absent/unparseable → `datetime.now(tz=utc)`,
  matching `_entry_published`'s fallback.
- `summary` from `.views-field-body .field-content` via `strip_html` + `truncate_sentences(…, 600)`,
  reusing the same `textutil` helpers as the RSS path.
- `guid = url`, `image_url = None`.

Category is then computed by the existing `classify(title, summary, [], feed.category)` — no feed
tags, keyword match, else the `news` fallback — identical to how RSS rows are classified.

### 4. Registry entry
```python
{
    "slug": "chattgov",
    "name": "City of Chattanooga",
    "homepage": "https://chattanooga.gov",
    "enabled": True,
    "feeds": [
        {
            "category": "news",
            "kind": "html",
            "url": "https://chattanooga.gov/stay-informed/latest-news",
        },
    ],
},
```

## Risks / Trade-offs

- **Markup fragility.** A scrape is coupled to chattanooga.gov's Drupal View markup; a redesign
  breaks it where an RSS contract would not. *Mitigation:* the existing per-feed `try/except` turns
  a parse failure into a recorded `last_status` on that one feed — visible in the sources footer,
  never aborting the cycle. `parse_html_listing` returns `[]` (not an exception) when it finds no
  rows, so an empty/changed page degrades to "no articles" rather than a crash; the fetcher reports
  it like the RSS "no entries" case.
- **No per-article images/bodies.** Listing-only scraping yields null `image_url` and a short
  teaser summary. Acceptable — several existing sources (The Pulse, the library) also carry no
  image, and the story cards already handle null images. Fetching article pages was explicitly
  deferred to keep network cost and scope down.
- **Second transport in one module.** Branching `fetch_feed` adds an `if kind` fork rather than a
  fully abstracted fetcher interface. Deliberate: with exactly one html source, a small branch is
  clearer than a plugin layer, and the two branches converge immediately on the shared
  `upsert_articles`.
- **Timezone parsing.** Relies on the `datetime[datetime]` attribute carrying an offset; the UTC
  conversion + `now()` fallback keeps a malformed timestamp from failing the whole feed.
