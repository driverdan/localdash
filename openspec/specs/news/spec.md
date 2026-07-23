# news Specification

## Purpose

Backend news aggregation, ported from ChattNews: a code registry of Chattanooga outlets and their
RSS feeds, scheduled fetching with per-feed error isolation, deduplicated article storage in
Postgres, cross-outlet story clustering, and the `/api/v1/news/` API (stories, sources, manual
refresh) that the `frontend-news` feature consumes.
## Requirements
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

### Requirement: Cross-outlet story clustering
After every fetch cycle, the system SHALL recluster articles published within the story window
(7 days) using the ported ChattNews algorithm: pairwise title similarity (token-set
Jaccard/containment with a sequence-similarity fallback, plus a distinctive-shared-tokens rule that
applies only across different outlets) merged with union-find, storing a shared `cluster_id` on
matched articles (the smallest member article id). Articles from the same outlet SHALL NOT be
merged by the distinctive-token rule alone (formulaic series headlines falsely match within one
outlet).

#### Scenario: Same story from two outlets clusters
- **WHEN** two outlets publish articles with closely matching titles about one event
- **THEN** both articles share a `cluster_id` and surface as one story

#### Scenario: Formulaic same-outlet headlines stay separate
- **WHEN** one outlet publishes a series of near-identical formulaic headlines about different
  subjects sharing distinctive tokens
- **THEN** the distinctive-token rule does not merge them into one cluster

### Requirement: Stories API
The system SHALL serve `GET /api/v1/news/stories?hours=N` (default 72, bounded by the story
window) returning the category slug→label map and one story object per cluster: headline from the
earliest article, summary from the wordiest member (sentence-truncated), category by majority vote
of members (a specific section beats generic `news` on ties), an `image_url` taken from the earliest
member that has one (null when no member has an image), first/latest published timestamps, source
and article counts, and one link per outlet (the outlet's own headline, URL, and published time),
sorted by latest activity descending. The endpoint SHALL accept an optional `limit` query
parameter (minimum 1): when present, at most `limit` stories are returned, taken from the front of
the sorted list; when absent, all stories in the window are returned as before.

#### Scenario: Story aggregates its outlets
- **WHEN** a cluster contains three articles from two outlets
- **THEN** its story lists exactly two source links (one per outlet) and reports
  `article_count: 3`, `source_count: 2`

#### Scenario: Hours filter bounds the feed
- **WHEN** a client requests `stories?hours=24`
- **THEN** only clusters with articles published in the last 24 hours are returned

#### Scenario: Limit bounds the story count
- **WHEN** the window contains eight stories and a client requests `stories?limit=5`
- **THEN** exactly the 5 stories with the newest activity are returned, still sorted latest-first,
  alongside the category map

#### Scenario: Omitted limit returns the full window
- **WHEN** a client requests `stories` without a `limit` parameter
- **THEN** every story in the window is returned, as before

#### Scenario: Story borrows the earliest member's image
- **WHEN** a cluster's earliest article has no image but a later member does
- **THEN** the story's `image_url` is that later member's image (the earliest member that has one)

#### Scenario: Story with no member images
- **WHEN** no article in a cluster has an `image_url`
- **THEN** the story's `image_url` is null

### Requirement: Sources API and manual refresh
The system SHALL serve `GET /api/v1/news/sources` returning one row per feed (source slug/name/
homepage/enabled, feed category, `last_fetch`, `last_status`, per-source-and-category article
count) for the feed-health footer, and `POST /api/v1/news/refresh` which runs a full fetch +
recluster cycle on demand and returns per-source results and the cluster count.

#### Scenario: Feed health is visible
- **WHEN** a client requests `GET /api/v1/news/sources` after a cycle in which one feed failed
- **THEN** that feed's row shows its error `last_status` while healthy feeds show success

#### Scenario: Manual refresh runs a full cycle
- **WHEN** a client sends `POST /api/v1/news/refresh`
- **THEN** feeds are fetched, articles reclustered, and the response reports the outcome

### Requirement: Per-article content categorization
The system SHALL assign each article's category from the article's own content, not solely from the
feed section it arrived in. The category SHALL be resolved by the following ordered rules, first
match wins, and the result SHALL be one of the normalized categories (`news`, `sports`, `business`,
`politics`, `opinion`, `life`):

1. **Mapped feed `<category>` tag** — when the feed item carries per-item `<category>` tags (exposed
   by feedparser as `entry.tags`) and at least one maps into a normalized category via a
   code-defined tag→category map (e.g. `Commentary`→`opinion`, `Local News`/`Top Stories`→`news`),
   the mapped category is used; a specific category wins over a generic `news` tag on the same item.
   Unmapped tags (geographic names, editorial flags, campaign names, free-text tags) SHALL be
   ignored. This rule SHALL be skipped entirely for articles from a source registered with
   `use_feed_tags: False` — such a source's tags are boilerplate applied to every post (e.g. the
   Chattanooga Public Library's `News`/`Featured`), not per-article topical signal.
2. **Keyword classification** — otherwise, a code-defined topic→keyword map is matched against the
   article's title and HTML-stripped summary (case-insensitive), following the existing events
   tagging pattern; the matched topic's category is used.
3. **Feed-section fallback** — otherwise, the article keeps its feed's registered category.

The tag→category and topic→keyword maps SHALL be defined in code (the source of truth), mirroring
the registry and events `tagging.py` conventions.

#### Scenario: Feed tag maps to opinion
- **WHEN** a News Chronicle item carries a `<category>` tag `Commentary`
- **THEN** the stored article's category is `opinion`, taken from the tag→category map ahead of
  keyword matching and the feed section

#### Scenario: Keyword match categorizes when no mapped tag exists
- **WHEN** an article carries no mapped feed `<category>` tag but its title/summary contains sports
  keywords
- **THEN** the stored article's category is `sports`, from keyword classification

#### Scenario: Unmapped tags and no keyword match fall back to the feed section
- **WHEN** an article's only feed `<category>` tags are unmappable (e.g. `Marion County`,
  `Featured`) and no topic keyword matches its title/summary
- **THEN** the stored article keeps its feed's registered category as the fallback

#### Scenario: Single-feed outlets are categorized individually
- **WHEN** The Pulse (a single `life` feed) publishes an article whose content matches business
  keywords
- **THEN** that article is stored as `business`, rather than every Pulse article collapsing into
  `life`

#### Scenario: A tag-exempt source ignores its boilerplate tags
- **WHEN** a Chattanooga Public Library article carries the `<category>` tags `News` and
  `Featured` and its title/summary matches no topic keyword
- **THEN** the stored article's category is `life` from the feed registration — the mapped `News`
  tag is not consulted because the source is registered with `use_feed_tags: False`

### Requirement: Sources API per-category counts under content categorization
Because article category is content-derived and no longer equals the producing feed's section, the
`GET /api/v1/news/sources` per-source article count SHALL be defined as a per-source total (articles
stored for that source) rather than a count of `article.category == feed.category`. Feed-health
fields (slug, name, homepage, enabled, feed category, `last_fetch`, `last_status`) SHALL remain
unchanged.

#### Scenario: Source count reflects all of a source's articles
- **WHEN** a source's articles are classified across several categories that differ from its feeds'
  sections
- **THEN** the sources response reports the source's total stored article count, not only those
  whose category matches a feed's registered category

