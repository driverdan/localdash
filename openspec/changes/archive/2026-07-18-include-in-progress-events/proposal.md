## Why

The events listing's `upcoming` filter keeps only events with a start time at or after now, so an
event disappears from the Events page and the homepage digest the moment it begins — even though
it may run for hours more. At a typical Saturday-afternoon snapshot, two dozen stored events were
in progress and invisible. A local dashboard should surface what is happening right now, not hide
it.

## What Changes

- The `upcoming` filter on `GET /api/v1/events/items` changes meaning from "starts at or after
  now" to "has not yet ended": events whose `ends_at` is still in the future remain listed after
  they start.
- Events with no `ends_at` (~12% of stored rows) keep today's behavior: they drop out of the
  default listing once their start time passes. No end time is invented for them.
- Ordering is unchanged (start time ascending), so in-progress events naturally sort first. The
  Events page and homepage digest inherit the new behavior with no frontend changes — both rely on
  the backend's `upcoming=true` default.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `events`: the "Events listing API" requirement's `upcoming` filter changes from "only events
  starting at or after now" to "only events that have not ended — end time in the future, or, for
  events without an end time, start time at or after now".

## Impact

- `app/api/events.py`: the `upcoming` predicate and its query-parameter description.
- `openspec/specs/events/spec.md`: the "Events listing API" requirement wording and its default
  listing scenario.
- Tests covering the `upcoming` filter.
- No frontend, schema, or migration changes. The `frontend-home` and `frontend-events` specs are
  untouched: they describe rendering whatever the items endpoint returns.
