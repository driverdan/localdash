## Why

The home page's "Upcoming events" widget reuses the events feature's full `EventCard` — tag
badges, feed image, venue/address, description, and source links — so five digest entries
dominate the right column and read as a second events page rather than an at-a-glance summary.
The digest only needs enough to answer "what's coming up, when, and how far away?"

## What Changes

- Replace the full `EventCard` reuse in the home events widget with a compact, home-owned
  digest component (following the `WeatherStrip` precedent) that renders, per event:
  - the event title, linked to the event's primary source URL (opens in a new tab)
  - the full formatted date/time (same `fmtEventDate(starts_at, ends_at)` output as the
    events page) plus the distance in miles when available
  - nothing else — no tags, image, venue, description, or source-link row
- Drop the widget body's `#events` id scoping and the home CSS rule that trimmed event card
  images, since the digest no longer inherits the events feature's card styling; style the
  digest rows in `home.css` instead.
- Update the `home.css` header comment describing the card-reuse contract to reflect that
  reuse applies where the digest is the full card (news), while home owns its own compact
  renderings otherwise (weather, events).
- Data flow is unchanged: same `GET /api/v1/events/items?limit=5` fetch, same home state,
  same live-update refetch behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-home`: the "Upcoming events digest widget" requirement changes from reusing the
  events feature's `EventCard` to rendering a home-owned abbreviated row (linked title,
  formatted date/time, distance). The cross-feature import rule in "Home feature namespace"
  narrows accordingly (the events feature now only supplies types, not a card component).

## Impact

- `frontend/src/features/home/components/HomePage.svelte` — render the new digest component
  instead of `EventCard`; remove the `#events` wrapper id.
- `frontend/src/features/home/components/` — new `EventDigest.svelte` (or similar) component.
- `frontend/src/styles/home.css` — digest row styles; remove the `#events` neutralization and
  image-trim rules for events; update the contract comment.
- `frontend/src/features/events/index.ts` — home may no longer need the `EventCard` export
  (news still reuses `StoryCard`; leave the events public surface intact for its own page).
- No backend, API, or state changes.
