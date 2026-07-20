## Why

Keyword tagging and source-supplied tags sometimes produce topics that are noise for this
deployment (irrelevant, overly broad, or mis-derived). There is no way to suppress such a tag: it
keeps getting re-created on every ingest and keeps appearing on events, in the `?topic=` filter,
and in the frontend tag combobox. Operators need a declarative way to say "this topic should never
exist here."

## What Changes

- Add a config setting `events_blocked_tags` (comma-separated topic names, empty by default),
  lowercased to match how tag names are stored.
- On application startup, delete every blocklisted tag from the `tags` table; the existing
  `event_tags` foreign-key cascade removes those tags from all events automatically.
- During ingest, strip blocklisted names from both the keyword-derived and the source-supplied tag
  sets before tags are created or attached, so a blocked tag is never re-created and never lands on
  a new or updated event.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `events`: the keyword topic tagging requirement gains blocklist filtering at ingest, and a new
  requirement covers startup purge of blocklisted tags plus the `events_blocked_tags` setting.

## Impact

- **Config**: new `events_blocked_tags` setting in `app/config.py`.
- **Ingest**: `app/events/ingest.py` filters blocked names out of the tag set applied to events.
- **Startup**: application lifespan (`app/main.py`) runs a one-shot delete of blocklisted tags.
- **Behavior, no schema change**: no migration — relies on the existing `event_tags` ON DELETE
  CASCADE. The `/api/v1/events/tags` list and `?topic=` filter surface blocked tags no longer
  because the rows are gone, not through new API-layer filtering.
