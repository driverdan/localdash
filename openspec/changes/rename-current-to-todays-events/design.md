## Context

The home page events widget (`HomePage.svelte` + `loadEvents()` in `home/api.ts`) fetches
`GET /api/v1/events/items?limit=10&max_miles=35` and renders up to 10 upcoming events, soonest
first, as abbreviated digest rows. The `/items` endpoint filters to `upcoming` events (those
whose `coalesce(ends_at, starts_at) >= now`, compared in UTC) and orders by `starts_at` ascending.

There is no app-level timezone: the backend runs entirely on UTC, while the deployment's center is
Chattanooga (Eastern). The one place "today" is already defined is the frontend: `fmtEventDate`
(`format.ts`) computes a whole-day diff between local midnights, so a row renders "Today" when the
event's start falls on the **viewer's local calendar day**.

This change scopes the widget to the current day while leaving the existing fetch and filtering
untouched.

## Goals / Non-Goals

**Goals:**
- Retitle the widget "Today's events" (heading + empty-state copy).
- Render only events that start on the viewer's current local calendar day.
- Keep the "today" boundary consistent with the "Today" label the rows already show.

**Non-Goals:**
- No backend/API change: the request URL, `upcoming` default, `max_miles=35`, `limit=10`, and
  ordering all stay as they are.
- No change to the existing start-time / distance filtering semantics — the day cap is layered on
  top of whatever the endpoint returns.
- No "ongoing today" (overlap) handling — an event that started on a previous day is out of scope
  even if still running today.

## Decisions

### Filter on the frontend, not the backend
Add the day cap in `loadEvents()` after the fetch, rather than a new endpoint parameter.
- *Why:* "Today" is inherently the viewer's local day, and the frontend already owns that concept
  (`fmtEventDate`). A backend filter would compute "today" in UTC (or require introducing an app
  timezone), which could disagree with the label the very same row renders.
- *Completeness:* items arrive sorted by `starts_at` ascending, so all of today's events precede
  any future ones; slicing to today never drops an earlier same-day event. `limit=10` stays a pure
  display cap.
- *Alternative considered:* a `?day=today` / date-window endpoint param — rejected as more surface
  area (endpoint logic + spec) with a timezone mismatch risk and no user-visible benefit here.

### "Starts today" (local calendar day), not "happening today"
Keep only items whose `starts_at`, in the viewer's local zone, falls on today's date.
- *Why:* simplest rule and an exact match for the "Today" text a row already shows. Including
  events that started earlier but are still running would surface rows labeled with a past date
  under a "Today's events" header. (Confirmed with the requester.)

### Extract the local-day check into a shared helper
Pull the local-midnight day-diff `fmtEventDate` already computes into a small helper in
`format.ts` (e.g. `isLocalToday(iso)` / a shared day-diff), and use it both for the label and the
filter.
- *Why:* one definition of "today" for the label and the filter guarantees they can't drift; the
  logic already exists and is just being lifted, not reinvented.

## Risks / Trade-offs

- **A day with no local-day events shows the empty state** even though upcoming events exist later
  this week → intended: the widget now answers "what's on today?", and "view all →" reaches the
  rest. Empty-state copy is updated to match.
- **Timezone is the viewer's, not Chattanooga's** → for a viewer physically elsewhere, "today"
  follows their browser, consistent with every other date the app renders via `toLocale*`. Not a
  regression; the app has always rendered event dates in the viewer's zone.
- **Requirement heading vs. widget title** → the spec requirement is renamed to "Today's events
  digest widget" to stay coherent with the new user-facing heading.
