## MODIFIED Requirements

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
