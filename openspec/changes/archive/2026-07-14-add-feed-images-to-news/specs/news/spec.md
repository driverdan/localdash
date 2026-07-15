## MODIFIED Requirements

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
