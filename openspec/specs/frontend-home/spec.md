# frontend-home Specification

## Purpose

The landing page served at `/`: a widget grid composing at-a-glance digest widgets — latest
news beside a right column of weather above upcoming events — all with independent, unfiltered
data fetches, and "view all" links into the full feature pages. A feature namespace under
`frontend/src/features/home/` that reuses the news card component through its public surface
and renders its own compact weather and events digests, designed so future widgets (timeseries
summary) are added as pure additions.
## Requirements
### Requirement: Home feature namespace
The home landing UI SHALL live in `frontend/src/features/home/`, following the established
feature layout (typed `api.ts` client, a runes store, components, and an `index.ts` public
surface exporting only the page component). It SHALL be mounted at the root route (`/`).
Cross-feature imports SHALL resolve only to other features' `index.ts` public surfaces (the
news feature's shared card component and the events feature's types), never to their internals.

#### Scenario: Home is an isolated feature
- **WHEN** imports under `frontend/src/features/home/` are inspected
- **THEN** every cross-feature import resolves to `features/news` or `features/events` public
  surfaces (`index.ts`), never to files inside those namespaces

### Requirement: Widget grid landing page
The home page SHALL render a grid of widget cards: a "Latest news" widget in the left column and,
in the right column, a weather widget above an "Upcoming events" widget. The news and events
widgets SHALL each have a heading and a "view all" link that navigates client-side (no full page
load) to `/news` and `/events` respectively. The grid SHALL use an auto-fitting column layout so
future widgets (timeseries summary) can be added as pure additions without restructuring the
page; the weather and events widgets SHALL share a single grid item (a column container) so they
count as one column of the auto-fit layout.

#### Scenario: View-all links navigate client-side
- **WHEN** the user clicks the news widget's "view all" link
- **THEN** the URL becomes `/news` and the full news feed renders without a full page load

#### Scenario: Widgets lay out as a grid
- **WHEN** the home page renders on a wide viewport
- **THEN** the news widget appears beside a right column containing the weather widget above the
  events widget; on a narrow viewport the widgets stack in the order news, weather, events

### Requirement: Latest news digest widget
The news widget SHALL fetch `GET /api/v1/news/stories?limit=5` into home-owned state and render
up to 5 stories, newest activity first, reusing the news feature's `StoryCard` component. The
category label map returned by the same response SHALL be applied so category badges show display
labels, even if the user has never visited `/news`. A failed load SHALL show an error message
inside the widget; an empty result SHALL show an empty-state message. Neither affects the other
widget.

#### Scenario: Five newest stories render
- **WHEN** the stories endpoint returns stories
- **THEN** the widget shows at most 5 story cards in the same newest-first order

#### Scenario: Category badges are labeled on a cold visit
- **WHEN** a user lands on `/` in a fresh browser session without ever visiting `/news`
- **THEN** story category badges show display labels (e.g. "Local news"), not raw slugs

#### Scenario: News failure does not break the events widget
- **WHEN** the stories request fails but the events request succeeds
- **THEN** the news widget shows an error message and the events widget renders its events

### Requirement: Upcoming events digest widget
The events widget SHALL fetch `GET /api/v1/events/items?limit=5` with no topic, distance, or
search parameters — ignoring any event filter preferences persisted by the events feature — and
render up to 5 upcoming events, soonest first, as abbreviated digest rows owned by the home
feature (not the events feature's `EventCard`). Each row SHALL show only: the event title linked
to the event's primary source URL (opening in a new tab; plain text when the event has no
links), and the full formatted date/time produced by the shared `fmtEventDate(starts_at,
ends_at)` formatter, followed by the distance in miles when `distance_miles` is non-null. Rows
SHALL NOT show tags, images, venue/address, descriptions, or a source-link list. A failed load
SHALL show an error message inside the widget; an empty result SHALL show an empty-state
message.

#### Scenario: Saved event filters are ignored
- **WHEN** the user has topic and distance filters saved from the events page and opens `/`
- **THEN** the widget's request carries no filter parameters and shows the next 5 events
  regardless of those saved filters

#### Scenario: Next five upcoming events render as abbreviated rows
- **WHEN** the events endpoint returns events
- **THEN** the widget shows at most 5 digest rows ordered by start time ascending, each showing
  only a linked title and a formatted date/time with distance — no tags, image, venue,
  description, or source-link list

#### Scenario: Title links to the primary source
- **WHEN** a digest row renders for an event whose first link has a source URL
- **THEN** the title is a link to that URL that opens in a new tab

#### Scenario: Distance is omitted when unknown
- **WHEN** a digest row renders for an event whose `distance_miles` is null
- **THEN** the row shows the formatted date/time with no distance fragment

#### Scenario: No upcoming events
- **WHEN** the events endpoint returns an empty list
- **THEN** the widget shows an empty-state message instead of a blank card

### Requirement: Styles via the global styling contract
Home styling SHALL follow the frontend styling contract: plain global CSS in
`frontend/src/styles/home.css`, imported from `main.ts`, using the shared theme variables so
themes and external overrides apply. Components SHALL NOT use scoped `<style>` blocks for
home-specific rules.

#### Scenario: Home styling is global and externally overridable
- **WHEN** the built CSS bundle is inspected
- **THEN** home's selectors (e.g. `.home-grid`, `.widget`) are plain global rules that a
  user-supplied stylesheet loaded after the bundle can override without extra specificity

### Requirement: Widgets refresh on live update signals
The home feature SHALL keep its widgets current via permanent subscriptions on the shared
live-update bus (see `frontend-live`), registered from the app shell: a `news` ping refetches the
stories digest, an `events` ping refetches the events digest, and a `weather` ping refetches the
weather strip. The same loaders SHALL run on bus reconnect. On-mount initial fetches and the
per-widget loaded/error flags are unchanged — a live refetch that fails leaves the previous widget
content in place rather than blanking it.

#### Scenario: Digest updates without a reload
- **WHEN** the user is viewing `/` and a news refresh cycle completes server-side
- **THEN** the stories digest refetches and shows the new stories without a page reload or
  navigation

#### Scenario: Weather strip follows the weather ping
- **WHEN** a `{topic: "weather", type: "updated"}` message arrives
- **THEN** the weather strip refetches `/api/v1/weather/current` and renders the fresh conditions

#### Scenario: Failed live refetch keeps previous content
- **WHEN** a ping-triggered digest refetch fails
- **THEN** the widget keeps showing its previous content

### Requirement: Weather widget
The home page SHALL render a weather widget inside the widget grid's right column, directly above
the "Upcoming events" widget. The weather and events widgets SHALL be wrapped in a single column
container that is one grid item, so the grid's auto-fit behavior is preserved (future top-level
widgets remain pure additions). The weather widget SHALL use the shared widget visual language: a
widget header reading "Weather" (with no view-all link, as there is no weather page), current
conditions first, then the forecast periods stacked vertically as rows. It SHALL fetch
`GET /api/v1/weather/current` into home-owned state, in parallel with the other widgets' fetches,
and render current conditions (temperature, description, icon, and an "as of" time from the
observation timestamp, so a lagging station reading is not presented as live) plus the returned
forecast periods labeled with their NWS-assigned period names — never a hardcoded "Today". A
failed load SHALL show a one-line notice inside the widget body and SHALL NOT affect the news or
events widgets; a partial response (missing `current` or empty `periods`) SHALL render whichever
half is present.

#### Scenario: Weather renders in the right column above events
- **WHEN** the home page renders on a wide viewport
- **THEN** the weather widget appears in the right column above the events widget, beside the
  news widget; on a narrow viewport the widgets stack in the order news, weather, events

#### Scenario: Weather looks like a widget
- **WHEN** the home page renders
- **THEN** the weather widget shows a "Weather" header matching the news/events widget headers,
  and forecast periods render as vertically stacked rows

#### Scenario: Period names come from the API
- **WHEN** the endpoint returns first periods named "Tonight" and "Wednesday" (an evening visit)
- **THEN** the widget labels the forecast "Tonight" and "Wednesday", not "Today"

#### Scenario: Observation age is visible
- **WHEN** the endpoint returns current conditions observed 45 minutes ago
- **THEN** the widget shows the observation's "as of" time alongside the conditions

#### Scenario: Weather failure does not break the other widgets
- **WHEN** the weather request fails but the news and events requests succeed
- **THEN** the weather widget shows a one-line notice and both other widgets render their content
  normally

