## MODIFIED Requirements

### Requirement: Config-managed tag blocklist
The system SHALL provide an `events_blocked_tags` configuration setting: a comma-separated list of
topic names, defaulting to `topics`. CitySpark's tag tree has a root named "Topics", and a root
tag resolves to its own name, so without this default every CitySpark event would carry a junk
`topics` tag. The deployment configuration (e.g. Docker Compose) SHALL NOT override this default
unless the operator sets the variable. Blocked names SHALL be lowercased and stripped of surrounding
whitespace, and empty entries SHALL be ignored, so the effective blocklist matches how tag names
are stored (the unique, case-sensitive, lowercase `tags` vocabulary). On application startup, the
system SHALL delete every `tags` row whose name is in the effective blocklist; the existing
`event_tags` foreign-key `ON DELETE CASCADE` SHALL remove those tags from all events, and no
database migration SHALL be required. When the effective blocklist is empty, startup SHALL delete
no tags.

#### Scenario: Default blocklist removes the CitySpark root tag
- **WHEN** the application runs with `events_blocked_tags` unset, including under the shipped
  Docker Compose configuration
- **THEN** the effective blocklist is `{topics}` and no event carries a `topics` tag

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
- **WHEN** `events_blocked_tags` is explicitly set to empty
- **THEN** application startup deletes no tags and existing tags are unaffected
