# news — delta for add-chattlibrary-sources

## MODIFIED Requirements

### Requirement: News source and feed registry
The news feature SHALL define its outlets and their per-section RSS feeds as a code registry
(sources with slug, name, homepage, enabled flag; feeds with URL and one normalized category each),
covering seven Chattanooga outlets (Chattanoogan.com, Chattanooga Times Free Press, WDEF News 12,
Local 3 News, Chattanooga News Chronicle, The Pulse, and the Chattanooga Public Library). A source
MAY register a single primary site feed instead of per-section feeds. The registry SHALL be the
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
  `https://chattlibrary.org/category/news/feed/`, registered with category `life`
