## MODIFIED Requirements

### Requirement: News source and feed registry
The news feature SHALL define its outlets and their per-section RSS feeds as a code registry
(sources with slug, name, homepage, enabled flag; feeds with URL and one normalized category each),
covering six Chattanooga outlets (Chattanoogan.com, Chattanooga Times Free Press, WDEF News 12,
Local 3 News, Chattanooga News Chronicle, and The Pulse). A source MAY register a single primary
site feed instead of per-section feeds, in which case all of that outlet's articles carry that
feed's category. The registry SHALL be the source of truth: at application startup it is upserted
into the database, and feeds removed from the registry SHALL be deleted so they stop being fetched.
Within a source, specific section feeds SHALL be ordered before the general news feed so an article
appearing in both keeps the specific category.

#### Scenario: Registry syncs to the database on startup
- **WHEN** the application starts after a feed URL was removed from the registry
- **THEN** that feed's row is deleted and it is not fetched, while registry sources/feeds are
  present with their configured category and order

#### Scenario: Section feed supplies the category
- **WHEN** an article appears in an outlet's sports section feed
- **THEN** it is stored with category `sports`, because feeds carry no per-item category tags

#### Scenario: Primary-feed outlet categorizes all articles under news
- **WHEN** Chattanooga News Chronicle is registered with only its primary site feed
  (`https://www.chattnewschronicle.com/feed/`) mapped to category `news`
- **THEN** every article fetched from that outlet is stored with category `news`, regardless of the
  per-item category tags the feed carries

#### Scenario: Arts weekly categorizes all articles under life
- **WHEN** The Pulse is registered with only its global site feed
  (`https://www.chattanoogapulse.com/api/rss/content.rss`) mapped to category `life`
- **THEN** every article fetched from that outlet is stored with category `life`, because the feed
  carries no per-item category tags and no section-scoped feeds are available
