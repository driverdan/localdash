## Context

The home "Current events" digest (`frontend/src/features/home/api.ts`, `loadEvents`) fetches
`GET /api/v1/events/items?limit=10` with no filters. The events API already supports a
`max_miles` query param and defaults the distance origin to `settings.center` when no `lat`/`lon`
is supplied, so the backend needs no change. This is a small, frontend-only adjustment.

## Goals / Non-Goals

**Goals:**
- Cap the home events digest at 35 miles from the configured center.

**Non-Goals:**
- Changing the `/events` page filtering or the user's persisted distance preference.
- Making the cap user-configurable or exposing it in settings.
- Any backend/API change.

## Decisions

- **Hardcode `max_miles=35` in the `loadEvents` request URL** rather than adding a config
  setting. The home digest already hardcodes `limit=10` and deliberately ignores persisted event
  filters, so a fixed homepage constant is consistent with how the widget already works.
  Alternative (a `settings`-backed value threaded to the frontend) was rejected as over-engineering
  for a single fixed digest tuning value.
- **Pass no `lat`/`lon`**, letting the API default the origin to `settings.center` — the same
  origin the events API and Meetup search already use.

## Risks / Trade-offs

- [Events with a NULL location drop out of the digest, since `ST_DWithin` fails for NULL] → This
  matches the events-page behavior when a distance filter is active and is acceptable: the digest
  is meant to show nearby, locatable events.
- [35 is a magic number] → Documented in the spec requirement and this design; a single constant
  in one call site is easy to find and change later.
