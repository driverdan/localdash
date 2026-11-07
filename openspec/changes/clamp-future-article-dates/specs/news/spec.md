## MODIFIED Requirements

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

The stored published time SHALL never be later than the article's fetch time: for every source and
for both `rss` and `html` feeds, an article whose feed-supplied date is later than its fetch time
SHALL be stored with `published` equal to its fetch time (no tolerance window). An article's
`published` and `fetched_at` SHALL be set when its row is first inserted and SHALL NOT be changed
by later re-fetches of the same `(source_id, guid)`. Existing rows that violate this cap SHALL be
corrected once by a data migration that sets `published = fetched_at` where `published >
fetched_at`.

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

#### Scenario: Future-dated feed item is capped at fetch time
- **WHEN** a feed item (from an `rss` or `html` feed, any source) carries a published date later
  than the time it is fetched
- **THEN** the stored article's `published` equals its `fetched_at`, so it sorts and ages from the
  moment it was first seen rather than staying at the top of the stories list

#### Scenario: Past-dated feed item keeps its feed date
- **WHEN** a feed item's published date is at or before the time it is fetched
- **THEN** the stored article's `published` is the feed-supplied date, unchanged

#### Scenario: Re-fetch does not move a capped article
- **WHEN** an article stored with a capped `published` is fetched again, including after its
  original future date has passed
- **THEN** its `published` and `fetched_at` are unchanged, so it does not jump back to the top of
  the stories list

#### Scenario: Backfill corrects already-stored future-dated rows
- **WHEN** the data migration runs against a table containing rows with `published > fetched_at`
  and rows with `published <= fetched_at`
- **THEN** every violating row has `published` set to its `fetched_at`, and every other row is
  unchanged
