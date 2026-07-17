# news — delta for add-chattlibrary-sources

## MODIFIED Requirements

### Requirement: News source and feed registry
The news feature SHALL define its outlets and their per-section RSS feeds as a code registry
(sources with slug, name, homepage, enabled flag; feeds with URL and one normalized category each),
covering seven Chattanooga outlets (Chattanoogan.com, Chattanooga Times Free Press, WDEF News 12,
Local 3 News, Chattanooga News Chronicle, The Pulse, and the Chattanooga Public Library). A source
MAY register a single primary site feed instead of per-section feeds, and MAY be registered with
`use_feed_tags: False` (default `True`) to declare that its feed's per-item `<category>` tags
carry no topical signal and must not drive categorization (see "Per-article content
categorization"). The registry SHALL be the
source of truth: at application startup it is upserted into the database, and feeds removed from
the registry SHALL be deleted so they stop being fetched. A feed's registered category SHALL serve
as the last-resort fallback category for its articles (see "Per-article content categorization"),
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
