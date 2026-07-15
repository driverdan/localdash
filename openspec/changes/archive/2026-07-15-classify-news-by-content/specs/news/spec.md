## MODIFIED Requirements

### Requirement: News source and feed registry
The news feature SHALL define its outlets and their per-section RSS feeds as a code registry
(sources with slug, name, homepage, enabled flag; feeds with URL and one normalized category each),
covering six Chattanooga outlets (Chattanoogan.com, Chattanooga Times Free Press, WDEF News 12,
Local 3 News, Chattanooga News Chronicle, and The Pulse). A source MAY register a single primary
site feed instead of per-section feeds. The registry SHALL be the source of truth: at application
startup it is upserted into the database, and feeds removed from the registry SHALL be deleted so
they stop being fetched. A feed's registered category SHALL serve as the last-resort fallback
category for its articles (see "Per-article content categorization"), not as the sole determinant.
Within a source, specific section feeds SHALL be ordered before the general news feed so the
feed-section fallback prefers the specific category when an article appears in both.

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

### Requirement: Article storage and deduplication
Fetched articles SHALL be stored in Postgres with source, GUID, URL, title, HTML-stripped summary,
category, published time, fetch time, and an optional feed-supplied `image_url`. The `image_url`
SHALL be taken from the item's first image `enclosure`, falling back to the first `<img>` in the
item's content/summary HTML, and SHALL be null when the feed item carries neither. No article page
is fetched to discover images (feed-supplied images only). Articles SHALL be deduplicated per source
by GUID: an upsert on `(source_id, guid)` inserts new articles and updates existing ones in place
(never duplicating the row). The category SHALL be recomputed by content categorization on every
fetch and written to the row, so a re-fetch reflects the current classification rather than a
one-way `news`→specific upgrade.

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

## ADDED Requirements

### Requirement: Per-article content categorization
The system SHALL assign each article's category from the article's own content, not solely from the
feed section it arrived in. The category SHALL be resolved by the following ordered rules, first
match wins, and the result SHALL be one of the normalized categories (`news`, `sports`, `business`,
`politics`, `opinion`, `life`):

1. **Mapped feed `<category>` tag** — when the feed item carries per-item `<category>` tags (exposed
   by feedparser as `entry.tags`) and at least one maps into a normalized category via a
   code-defined tag→category map (e.g. `Commentary`→`opinion`, `Local News`/`Top Stories`→`news`),
   the first such mapped category is used. Unmapped tags (geographic names, editorial flags,
   campaign names, free-text tags) SHALL be ignored.
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
