## Context

The home page (`frontend/src/features/home/`) composes compact digest widgets. One widget shows a
short events list, currently labeled "Upcoming events" and populated by
`loadEvents()` in `api.ts`, which requests `GET /api/v1/events/items?limit=5`. This change is a
copy + count tweak confined to the home feature; the events API already accepts an arbitrary
`limit`, so no backend work is involved.

## Goals / Non-Goals

**Goals:**
- Change the widget heading to "Current events".
- Show up to 10 events instead of 5.
- Keep the digest's existing row format, filtering behavior, and live-update wiring unchanged.

**Non-Goals:**
- No changes to the events feature page (`/events`), the events API, or backend limits.
- No changes to the digest row layout, the "View all →" link, or empty/error states beyond copy.

## Decisions

- **Bump the `limit` query param 5 → 10 in `loadEvents()`** rather than introducing a config knob.
  The count is a single call site and there is no requirement for it to be configurable; a literal
  keeps the change minimal and matches the sibling news digest's inline `limit=5`.
- **Rename only the user-facing label and the requirement, not the events domain semantics.** The
  widget still requests soonest-first events with no filters; "Current events" is purely the
  display name, so only the `<h2>` text (and the consistent empty-state notice copy) changes.

## Risks / Trade-offs

- [A taller list could crowd the right-hand widget column on small viewports] → Rows are compact
  single-line digest entries and the column already scrolls with page content; 10 rows stays within
  the existing layout without new styling.
- [Requesting 10 when fewer exist] → The endpoint returns fewer than `limit` when appropriate and
  the empty-state path is unchanged, so no behavioral edge cases arise.

## Migration Plan

Frontend-only, backward-compatible. Ship by rebuilding the frontend (`npm run build`) — served
from `static/`. Rollback is reverting the two edited files. No data migration.

## Open Questions

None.
