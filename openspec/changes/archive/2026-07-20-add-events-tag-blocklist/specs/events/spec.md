## ADDED Requirements

### Requirement: Config-managed tag blocklist
The system SHALL provide an `events_blocked_tags` configuration setting: a comma-separated list of
topic names, defaulting to empty. Blocked names SHALL be lowercased and stripped of surrounding
whitespace, and empty entries SHALL be ignored, so the effective blocklist matches how tag names
are stored (the unique, case-sensitive, lowercase `tags` vocabulary). On application startup, the
system SHALL delete every `tags` row whose name is in the effective blocklist; the existing
`event_tags` foreign-key `ON DELETE CASCADE` SHALL remove those tags from all events, and no
database migration SHALL be required. When the effective blocklist is empty, startup SHALL delete
no tags.

#### Scenario: Startup purges blocked tags from the table and from events
- **WHEN** `events_blocked_tags` contains `politics` and the database holds a `politics` tag
  attached to several events
- **THEN** application startup deletes the `politics` tag row and its `event_tags` associations, so
  no event carries `politics` and `/api/v1/events/tags` no longer lists it

#### Scenario: Blocklist entries are normalized
- **WHEN** `events_blocked_tags` is set to ` Politics , , MUSIC ` (mixed case, blank entry,
  surrounding whitespace)
- **THEN** the effective blocklist is `{politics, music}` and both tags are purged at startup

#### Scenario: Empty blocklist is a no-op
- **WHEN** `events_blocked_tags` is empty
- **THEN** application startup deletes no tags and existing tags are unaffected

## MODIFIED Requirements

### Requirement: Keyword topic tagging
The system SHALL tag each newly created event that its source did not supply tags for, by
case-insensitive keyword matching of its title and description against a code-defined
topic→keywords map (topics: music, food, arts, outdoors, family, sports, tech, community,
education, nightlife, cars). The `cars` topic SHALL match automotive-event phrasing — at minimum
the keywords "car show", "cruise-in", "cruise in", "cars and coffee", "car meet", "hot rod",
"classic car", "corvette", "mustang", "camaro", and "auto show" — and SHALL NOT use the bare
substring "car" (to avoid false positives such as "carnival"). When a source supplies tags, those
tags SHALL be used as reported and keyword matching SHALL NOT be applied to that event.
Source-supplied tag names SHALL be lowercased before storage so they merge with the keyword topic
vocabulary rather than creating case-variant duplicates in the unique, case-sensitive `tags` table.
Before tags are created or attached, the ingest pipeline SHALL remove any name present in the
effective `events_blocked_tags` blocklist from the tag set — for both keyword-derived and
source-supplied tags — so a blocked tag is never created and never attached to a new or updated
event. Tags SHALL be stored as rows in a `tags` table joined many-to-many to events, and an event
may carry zero or many tags. Tag creation SHALL be idempotent under concurrent ingest.

#### Scenario: Title keywords produce tags
- **WHEN** an event titled "Live music and food trucks" with no source-supplied tags is ingested
- **THEN** it is tagged `music` and `food`

#### Scenario: Car events are tagged cars
- **WHEN** an event titled "Ooltewah Cruise In @ Cambridge Square" with no source-supplied tags is
  ingested
- **THEN** it is tagged `cars`

#### Scenario: Blocked keyword-derived tags are stripped at ingest
- **WHEN** `events_blocked_tags` contains `food` and an event titled "Live music and food trucks"
  with no source-supplied tags is ingested
- **THEN** it is tagged `music` only, and no `food` tag is created or attached

#### Scenario: Blocked source-supplied tags are stripped at ingest
- **WHEN** `events_blocked_tags` contains `nightlife` and a source reports an event carrying tags
  `["Nightlife", "Music"]`
- **THEN** the event is tagged `music` only, and no `nightlife` tag is created or attached
