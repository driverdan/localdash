## MODIFIED Requirements

### Requirement: News source and feed registry
The news feature SHALL define its outlets and their per-section feeds as a code registry
(sources with slug, name, homepage, enabled flag; feeds with URL, one normalized category each,
and a `kind` of `rss` or `html`), covering nine Chattanooga outlets (Chattanoogan.com,
Chattanooga Times Free Press, WDEF News 12, Local 3 News, Chattanooga News Chronicle, The Pulse,
the Chattanooga Public Library, the City of Chattanooga, and WTVC NewsChannel 9). A feed's `kind`
SHALL default to `rss`; a `kind: html` feed declares that its URL is a server-rendered listing
page to be scraped rather than an RSS feed to be parsed (see "Scheduled feed fetching with
per-feed error isolation"). A source MAY register a single primary site feed instead of
per-section feeds, and MAY be registered with `use_feed_tags: False` (default `True`) to declare
that its feed's per-item `<category>` tags carry no topical signal and must not drive
categorization (see "Per-article content categorization"). The registry SHALL be the source of
truth: at application startup it is upserted into the database, and feeds removed from the
registry SHALL be deleted so they stop being fetched. A feed's registered category SHALL serve as
the last-resort fallback category for its articles (see "Per-article content categorization"),
not as the sole determinant. Within a source, specific section feeds SHALL be ordered before the
general news feed so the feed-section fallback prefers the specific category when an article
appears in both.

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

#### Scenario: WTVC NewsChannel 9 registers a single tag-exempt local news feed
- **WHEN** the application starts with the default registry
- **THEN** the `wtvc` source ("NewsChannel 9 (WTVC)", homepage `https://newschannel9.com`) is
  present with exactly one feed, `https://newschannel9.com/news/local.rss`, registered with
  category `news`, the default `kind: rss`, and `use_feed_tags: False` (Sinclair tags every item
  `<category>article</category>`, a content type rather than a topic), and its articles are
  categorized by keyword with `news` as the fallback

#### Scenario: A feed defaults to rss kind
- **WHEN** a feed is registered without an explicit `kind`
- **THEN** it is treated as `kind: rss` and fetched via the RSS/feedparser path, exactly as before
