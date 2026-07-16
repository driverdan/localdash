# frontend-events — delta for add-event-images

## MODIFIED Requirements

### Requirement: Event list with source links
The events page SHALL render matching events as a list ordered by start time, each entry showing
the title, start time (and end time when present), venue/address when present, its topic tags,
its distance in miles when located, and one outbound link per reporting source. When the event has
an `image_url`, the card SHALL render it as a lazily loaded lead image (decorative — empty alt
text), following the news story card's conditional-image pattern; an event without an image SHALL
render exactly as before, with no reserved empty image region. When no events match — including
the not-yet-any-sources state — the page SHALL show an explicit empty state rather than a blank
region.

#### Scenario: Event card content
- **WHEN** an event with two source links is rendered
- **THEN** its card shows title, time, venue, tags, distance, and two labeled links, one per source

#### Scenario: Event card with an image
- **WHEN** an event whose `image_url` is set is rendered
- **THEN** its card shows the image, loaded lazily, alongside the existing text content

#### Scenario: Event card without an image
- **WHEN** an event whose `image_url` is null is rendered
- **THEN** its card shows no image element and no empty placeholder region

#### Scenario: Empty state
- **WHEN** the API returns zero items
- **THEN** the page shows an empty-state message instead of an empty list
