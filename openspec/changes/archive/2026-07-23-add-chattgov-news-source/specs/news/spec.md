## MODIFIED Requirements

### Requirement: News source and feed registry
The news feature SHALL define its outlets and their per-section feeds as a code registry
(sources with slug, name, homepage, enabled flag; feeds with URL, one normalized category each,
and a `kind` of `rss` or `html`), covering eight Chattanooga outlets (Chattanoogan.com,
Chattanooga Times Free Press, WDEF News 12, Local 3 News, Chattanooga News Chronicle, The Pulse,
the Chattanooga Public Library, and the City of Chattanooga). A feed's `kind` SHALL default to
`rss`; a `kind: html` feed declares that its URL is a server-rendered listing page to be scraped
rather than an RSS feed to be parsed (see "Scheduled feed fetching with per-feed error isolation").
A source MAY register a single primary site feed instead of per-section feeds, and MAY be
registered with `use_feed_tags: False` (default `True`) to declare that its feed's per-item
`<category>` tags carry no topical signal and must not drive categorization (see "Per-article
content categorization"). The registry SHALL be the source of truth: at application startup it is
upserted into the database, and feeds removed from the registry SHALL be deleted so they stop
being fetched. A feed's registered category SHALL serve as the last-resort fallback category for
its articles (see "Per-article content categorization"), not as the sole determinant. Within a
source, specific section feeds SHALL be ordered before the general news feed so the feed-section
fallback prefers the specific category when an article appears in both.

#### Scenario: Registry syncs to the database on startup
- **WHEN** the application starts after a feed URL was removed from the registry
- **THEN** that feed's row is deleted and it is not fetched, while registry sources/feeds are
  present with their configured category and order

#### Scenario: Section feed supplies the fallback category
- **WHEN** an article from an outlet's sports section feed matches no feed-tag prior and no keyword
- **THEN** it is stored with category `sports` from its feed section, as the last-resort fallback

#### Scenario: Content overrides the feed section
- **WHEN** an article arrives via an outlet's general `news` feed but its title/summary clearly
  describes a sporting event (keyword match) or carries a mapped feed `<category>` tag
- **THEN** it is stored with the content-derived category (e.g. `sports` or the tag-mapped
  category), not the feed's `news` section

#### Scenario: Chattanooga Public Library registers a single life-category feed
- **WHEN** the application starts with the default registry
- **THEN** the `chattlibrary` source is present with exactly one feed,
  `https://chattlibrary.org/category/news/feed/`, registered with category `life` and
  `use_feed_tags: False` (its WordPress taxonomy tags every post `News`/`Featured`, which would
  otherwise misfile every announcement under `news`)

#### Scenario: City of Chattanooga registers a single html-kind news feed
- **WHEN** the application starts with the default registry
- **THEN** the `chattgov` source ("City of Chattanooga") is present with exactly one feed,
  `https://chattanooga.gov/stay-informed/latest-news`, registered with category `news` and
  `kind: html` (the page is a Drupal View with no usable RSS feed)

#### Scenario: A feed defaults to rss kind
- **WHEN** a feed is registered without an explicit `kind`
- **THEN** it is treated as `kind: rss` and fetched via the RSS/feedparser path, exactly as before

### Requirement: Scheduled feed fetching with per-feed error isolation
The system SHALL fetch all enabled feeds on a configurable interval (default 15 minutes) as a
scheduled background job, and immediately once at startup. Fetching SHALL branch on each feed's
`kind`: an `rss` feed is fetched and parsed with `feedparser` (unchanged); an `html` feed is
fetched with `httpx` and its articles are parsed from the server-rendered listing HTML with
BeautifulSoup — one listing row per article, extracting title, absolute article URL, published
datetime (normalized to UTC), and summary. Only the listing page SHALL be fetched for an `html`
feed; individual article pages SHALL NOT be fetched. Both paths SHALL apply the same per-feed error
isolation: a feed that errors SHALL NOT abort the cycle — the failure is caught per-feed and
recorded on that feed's `last_status`, and every fetch updates the feed's `last_fetch`/`last_status`
telemetry. Requests on both paths SHALL send a mainstream browser User-Agent string (TownNews-hosted
RSS feeds rate-limit unfamiliar UAs with HTTP 429; the scrape reuses the same UA). Scheduled and
manual refreshes SHALL be serialized so two refresh cycles never run concurrently. Every completed
fetch+recluster cycle SHALL broadcast a `news` update ping on the global live-update bus (see
`live-updates`), from the code path shared by the scheduled job and the manual refresh so both
trigger it identically; a failed cycle broadcasts nothing.

#### Scenario: One dead feed does not stop the others
- **WHEN** one feed returns an error during a refresh cycle
- **THEN** the remaining feeds are still fetched, and the failing feed's `last_status` records the
  error

#### Scenario: An html feed is scraped rather than RSS-parsed
- **WHEN** a `kind: html` feed is fetched during a refresh cycle
- **THEN** its listing page is retrieved with `httpx` and parsed with BeautifulSoup into articles,
  no individual article page is fetched, and `feedparser` is not invoked for that feed

#### Scenario: A broken scrape isolates like any feed error
- **WHEN** a `kind: html` feed's listing page returns a non-success status or its expected markup is
  absent
- **THEN** the error is caught for that feed alone, recorded on its `last_status`, and the remaining
  feeds are still fetched

#### Scenario: Concurrent refreshes are serialized
- **WHEN** a manual refresh is requested while the scheduled refresh is running
- **THEN** the manual refresh waits for the running cycle rather than interleaving with it

#### Scenario: Completed cycle emits update ping
- **WHEN** a scheduled or manual refresh cycle completes
- **THEN** a `{topic: "news", type: "updated"}` message is broadcast on `/api/v1/ws`

### Requirement: Article storage and deduplication
Fetched articles SHALL be stored in Postgres with source, GUID, URL, title, HTML-stripped summary,
category, published time, fetch time, and an optional feed-supplied `image_url`. For an `rss` feed
the `image_url` SHALL be taken from the item's first image `enclosure`, falling back to the first
`<img>` in the item's content/summary HTML, and SHALL be null when the feed item carries neither.
For an `html` (scraped) feed the `image_url` SHALL be null and the GUID SHALL be the article URL.
No article page is fetched to discover images (feed-supplied or listing-supplied images only).
Articles SHALL be deduplicated per source by GUID: an upsert on `(source_id, guid)` inserts new
articles and updates existing ones in place (never duplicating the row). The category SHALL be
recomputed by content categorization on every fetch and written to the row, so a re-fetch reflects
the current classification rather than a one-way `news`→specific upgrade.

#### Scenario: Same article in two feeds keeps its content category
- **WHEN** the same GUID arrives from an outlet's general news feed and later its politics feed
- **THEN** one article row exists whose category is the content-derived category (feed-tag prior or
  keyword match), independent of which feed delivered it

#### Scenario: Repeat fetch is idempotent
- **WHEN** a refresh fetches articles already stored
- **THEN** no duplicate rows are created and each row's category reflects the current classification

#### Scenario: Image enclosure is captured
- **WHEN** a feed item includes an image `enclosure`
- **THEN** the stored article's `image_url` is that enclosure URL

#### Scenario: Inline image is the fallback
- **WHEN** a feed item has no image `enclosure` but its content/summary HTML contains an `<img>`
- **THEN** the stored article's `image_url` is that image's `src`

#### Scenario: No image in the feed item
- **WHEN** a feed item carries neither an image `enclosure` nor an inline `<img>`
- **THEN** the stored article's `image_url` is null

#### Scenario: Scraped article stores URL as GUID and null image
- **WHEN** an article is scraped from a `kind: html` listing page
- **THEN** its stored row has `guid` equal to the article URL and `image_url` null, and re-fetching
  the same listing produces no duplicate row (upsert on `(source_id, guid)`)
