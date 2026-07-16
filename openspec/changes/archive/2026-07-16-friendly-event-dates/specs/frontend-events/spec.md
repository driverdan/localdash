## MODIFIED Requirements

### Requirement: Event list with source links
The events page SHALL render matching events as a list ordered by start time, each entry showing
the title, start date and time (and end time when present), venue/address when present, its topic
tags, its distance in miles when located, and one outbound link per reporting source. When the
event has an `image_url`, the card SHALL render it as a lazily loaded lead image (decorative —
empty alt text), following the news story card's conditional-image pattern; an event without an
image SHALL render exactly as before, with no reserved empty image region. When no events match —
including the not-yet-any-sources state — the page SHALL show an explicit empty state rather than
a blank region.

The start date SHALL render as natural language relative to the viewer's local calendar day:
`Today` for the same day, `Tomorrow` for the next day, the weekday name (e.g. `Saturday`) for
events 2–6 days out, and a formatted date (e.g. `Sat, Jul 25`) for events 7 or more days out,
including the year only when it differs from the current year. Times SHALL render without
seconds, with the end time appended when present, e.g. `Today · 7:00 PM – 9:00 PM`.

#### Scenario: Event card content
- **WHEN** an event with two source links is rendered
- **THEN** its card shows title, date and time, venue, tags, distance, and two labeled links, one per source

#### Scenario: Event starting the same local day
- **WHEN** an event starting later on the current local calendar day is rendered
- **THEN** its date shows as `Today` followed by the seconds-free start time

#### Scenario: Event starting the next local day
- **WHEN** an event starting on the next local calendar day is rendered
- **THEN** its date shows as `Tomorrow` followed by the seconds-free start time

#### Scenario: Event within the week
- **WHEN** an event starting 2–6 local calendar days from now is rendered
- **THEN** its date shows as the weekday name (e.g. `Saturday`) followed by the start time

#### Scenario: Event a week or more away
- **WHEN** an event starting 7 or more local calendar days from now is rendered
- **THEN** its date shows as a formatted date (e.g. `Sat, Jul 25`), with the year included only
  when it differs from the current year

#### Scenario: Event with an end time
- **WHEN** an event whose `ends_at` is set is rendered
- **THEN** the end time is appended after an en dash, e.g. `Today · 7:00 PM – 9:00 PM`, with no
  seconds shown

#### Scenario: Event card with an image
- **WHEN** an event whose `image_url` is set is rendered
- **THEN** its card shows the image, loaded lazily, alongside the existing text content

#### Scenario: Event card without an image
- **WHEN** an event whose `image_url` is null is rendered
- **THEN** its card shows no image element and no empty placeholder region

#### Scenario: Empty state
- **WHEN** the API returns zero items
- **THEN** the page shows an empty-state message instead of an empty list
