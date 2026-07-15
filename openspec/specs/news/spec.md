# news Specification

## Purpose

Backend news aggregation, ported from ChattNews: a code registry of Chattanooga outlets and their
RSS feeds, scheduled fetching with per-feed error isolation, deduplicated article storage in
Postgres, cross-outlet story clustering, and the `/api/v1/news/` API (stories, sources, manual
refresh) that the `frontend-news` feature consumes.

## Requirements

### Requirement: News source and feed registry
The news feature SHALL define its outlets and their per-section RSS feeds as a code registry
(sources with slug, name, homepage, enabled flag; feeds with URL and one normalized category each),
covering the four Chattanooga outlets ported from ChattNews (Chattanoogan.com, Chattanooga Times
Free Press, WDEF News 12, Local 3 News). The registry SHALL be the source of truth: at application
startup it is upserted into the database, and feeds removed from the registry SHALL be deleted so
they stop being fetched. Within a source, specific section feeds SHALL be ordered before the
general news feed so an article appearing in both keeps the specific category.

#### Scenario: Registry syncs to the database on startup
- **WHEN** the application starts after a feed URL was removed from the registry
- **THEN** that feed's row is deleted and it is not fetched, while registry sources/feeds are
  present with their configured category and order

#### Scenario: Section feed supplies the category
- **WHEN** an article appears in an outlet's sports section feed
- **THEN** it is stored with category `sports`, because feeds carry no per-item category tags

### Requirement: Scheduled feed fetching with per-feed error isolation
The system SHALL fetch all enabled feeds on a configurable interval (default 15 minutes) as a
scheduled background job, and immediately once at startup. A feed that errors SHALL NOT abort the
cycle: the failure is caught per-feed and recorded on that feed's `last_status`, and every fetch
updates the feed's `last_fetch`/`last_status` telemetry. Requests SHALL send a mainstream browser
User-Agent string (TownNews-hosted feeds rate-limit unfamiliar UAs with HTTP 429). Scheduled and
manual refreshes SHALL be serialized so two refresh cycles never run concurrently.

#### Scenario: One dead feed does not stop the others
- **WHEN** one feed returns an error during a refresh cycle
- **THEN** the remaining feeds are still fetched, and the failing feed's `last_status` records the
  error

#### Scenario: Concurrent refreshes are serialized
- **WHEN** a manual refresh is requested while the scheduled refresh is running
- **THEN** the manual refresh waits for the running cycle rather than interleaving with it

### Requirement: Article storage and deduplication
Fetched articles SHALL be stored in Postgres with source, GUID, URL, title, HTML-stripped summary,
category, published time, fetch time, and an optional feed-supplied `image_url`. The `image_url`
SHALL be taken from the item's first image `enclosure`, falling back to the first `<img>` in the
item's content/summary HTML, and SHALL be null when the feed item carries neither. No article page
is fetched to discover images (feed-supplied images only). Articles SHALL be deduplicated per source
by GUID: an upsert on `(source_id, guid)` inserts new articles and, for existing ones, only upgrades
a generic `news` category to a specific section category (never the reverse, and never duplicating
the row).

#### Scenario: Same article in two section feeds
- **WHEN** the same GUID arrives from an outlet's general news feed and later its politics feed
- **THEN** one article row exists with category `politics`

#### Scenario: Repeat fetch is idempotent
- **WHEN** a refresh fetches articles already stored
- **THEN** no duplicate rows are created

#### Scenario: Image enclosure is captured
- **WHEN** a feed item includes an image `enclosure`
- **THEN** the stored article's `image_url` is that enclosure URL

#### Scenario: Inline image is the fallback
- **WHEN** a feed item has no image `enclosure` but its content/summary HTML contains an `<img>`
- **THEN** the stored article's `image_url` is that image's `src`

#### Scenario: No image in the feed item
- **WHEN** a feed item carries neither an image `enclosure` nor an inline `<img>`
- **THEN** the stored article's `image_url` is null

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
sorted by latest activity descending.

#### Scenario: Story aggregates its outlets
- **WHEN** a cluster contains three articles from two outlets
- **THEN** its story lists exactly two source links (one per outlet) and reports
  `article_count: 3`, `source_count: 2`

#### Scenario: Hours filter bounds the feed
- **WHEN** a client requests `stories?hours=24`
- **THEN** only clusters with articles published in the last 24 hours are returned

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
