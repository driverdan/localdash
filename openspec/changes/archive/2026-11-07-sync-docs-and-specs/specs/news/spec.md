## MODIFIED Requirements

### Requirement: Cross-outlet story clustering
After every fetch cycle, the system SHALL recluster articles published within the story window
(7 days) so that articles reporting the **same event** share a `cluster_id`, and articles that
only share a topic do not. A story's `cluster_id` SHALL be its smallest member article id.
Clustering SHALL use only article data already stored (title, summary, outlet, published time).
It SHALL NOT call external services or language models.

Similarity SHALL be computed from tokens weighted by their rarity (inverse document frequency)
across recent articles. Widely used words therefore contribute little evidence, and rare words
such as names, places and numbers contribute a lot. Numeric tokens SHALL be kept as tokens.

The system SHALL apply these rules:

- **Story time window.** An article SHALL join an existing story only if it was published no more
  than 36 hours after that story's earliest article. Later reports, including follow-ups, SHALL
  start a new story.
- **Majority match.** An article SHALL join an existing story only if it matches at least half of
  that story's current members. For a story of three or more members one matching member is not
  enough, so a single weak pairwise match cannot chain separate stories together; a one- or
  two-member story is joined by a single match.
- **Number veto.** Two articles SHALL NOT match when both titles contain numbers (excluding
  four-digit years) and they share none.
- **Summary veto.** When both articles have a non-trivial summary, two articles SHALL NOT match if
  their summaries share almost no weighted vocabulary, even when their titles are similar.
- **Same-outlet merging.** Articles from the same outlet SHALL be eligible to merge under the same
  rules as articles from different outlets.
- **Recurring-column exception.** Two articles from the same outlet with identical titles
  (ignoring case, punctuation, whitespace and a trailing plural "s") published more than 12
  hours apart SHALL NOT match.

Clustering SHALL be deterministic: the same set of articles SHALL always produce the same
clusters.

#### Scenario: Same story from two outlets clusters
- **WHEN** two outlets publish articles about one event within 36 hours whose titles share its
  specific details (e.g. "46-year-old killed in wrong-way crash on Highway 27" and "Person Killed
  In Wrong-Way Crash On Highway 27")
- **THEN** both articles share a `cluster_id` and surface as one story

#### Scenario: Formulaic same-outlet headlines stay separate
- **WHEN** one outlet publishes a series of templated headlines about different subjects (e.g.
  "DECISION 2026: Tennessee State House Dist. 23" and "DECISION 2026: Tennessee State House
  Dist. 24")
- **THEN** they are not merged into one cluster

#### Scenario: Shared generic words do not merge different events
- **WHEN** two articles share only common words (e.g. "Man in critical condition following
  officer-involved shooting at Chickamauga Dam" and "Man, 42, Hit While Crossing Lee Highway On
  Friday Night Is In Critical Condition")
- **THEN** they are placed in different clusters

#### Scenario: Weak link does not chain two stories together
- **WHEN** story A holds three articles, and a new article matches exactly one of them and also
  matches articles in story B
- **THEN** the new article does not join story A, and stories A and B are never merged through it

#### Scenario: Follow-up after the story window starts a new story
- **WHEN** an outlet publishes "Man Hit by Vehicle on Lee Hwy Dies from Injuries" more than 36
  hours after the earliest article of the original Lee Hwy story
- **THEN** it is placed in a new cluster, not the original story's cluster

#### Scenario: Recurring same-title column stays separate
- **WHEN** one outlet publishes "Latest Hamilton County Arrest Report" on consecutive days, more
  than 12 hours apart, including a day titled "Latest Hamilton County Arrest Reports"
- **THEN** each post is in its own cluster

#### Scenario: Same-outlet duplicate merges
- **WHEN** one outlet publishes two near-identical titles about the same event within 12 hours
  (e.g. a re-post or a corrected headline)
- **THEN** both articles share a `cluster_id`

#### Scenario: Clustering is measured against a labeled fixture
- **WHEN** the clustering test suite runs against the committed fixture of real articles with
  hand-assigned story groupings
- **THEN** the pairwise precision and recall of the produced clusters both meet the targets
  recorded in the test

### Requirement: Stories API
The system SHALL serve `GET /api/v1/news/stories?hours=N` (default 72, bounded by the story
window) returning the category slug→label map and one story object per cluster with at least one article
published inside the window. Story aggregates SHALL be computed over the cluster's members published
inside the window only: headline from the earliest such article, summary from the wordiest member (sentence-truncated), category by majority vote
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

#### Scenario: Aggregates cover only in-window members
- **WHEN** a cluster has one article published 30 hours ago and two published in the last 24 hours,
  and a client requests `stories?hours=24`
- **THEN** that story's headline, first-published time, counts, and links come only from the two
  in-window articles

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
