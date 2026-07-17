# frontend-home Specification

## Purpose

The landing page served at `/`: a full-width weather strip above a widget grid composing
at-a-glance digest cards (latest news, upcoming events), all with independent, unfiltered data
fetches, and "view all" links into the full feature pages. A feature namespace under
`frontend/src/features/home/` that reuses the news and events card components through their
public surfaces, and is designed so future widgets (timeseries summary) are added as pure
additions.

## Requirements

### Requirement: Home feature namespace
The home landing UI SHALL live in `frontend/src/features/home/`, following the established
feature layout (typed `api.ts` client, a runes store, components, and an `index.ts` public
surface exporting only the page component). It SHALL be mounted at the root route (`/`).
Cross-feature imports SHALL resolve only to other features' `index.ts` public surfaces (for the
shared card components), never to their internals.

#### Scenario: Home is an isolated feature
- **WHEN** imports under `frontend/src/features/home/` are inspected
- **THEN** every cross-feature import resolves to `features/news` or `features/events` public
  surfaces (`index.ts`), never to files inside those namespaces

### Requirement: Widget grid landing page
The home page SHALL render a full-width weather strip followed by a grid of widget cards: a
"Latest news" widget and an "Upcoming events" widget. The news and events widgets SHALL each have
a heading and a "view all" link that navigates client-side (no full page load) to `/news` and
`/events` respectively. The grid SHALL use an auto-fitting column layout so future widgets
(timeseries summary) can be added as pure additions without restructuring the page.

#### Scenario: View-all links navigate client-side
- **WHEN** the user clicks the news widget's "view all" link
- **THEN** the URL becomes `/news` and the full news feed renders without a full page load

#### Scenario: Widgets lay out as a grid
- **WHEN** the home page renders on a wide viewport
- **THEN** the news and events widgets appear side by side; on a narrow viewport they stack

### Requirement: Current weather strip
The home page SHALL render a weather strip above the widget grid, spanning the content column's
full width (above the news and events widgets at every viewport size; it sits beside the grid
rather than inside it, because a full-width item spanning an auto-fit grid pins its empty
trailing tracks open and squeezes the widgets). The strip SHALL fetch
`GET /api/v1/weather/current` into home-owned state, in parallel with the other widgets'
fetches, and render current conditions (temperature, description, icon, and an "as of" time from
the observation timestamp, so a lagging station reading is not presented as live) plus the
returned forecast periods labeled with their NWS-assigned period names — never a hardcoded
"Today". A failed load SHALL collapse the strip to a one-line notice (no layout hole) and SHALL
NOT affect the news or events widgets; a partial response (missing `current` or empty `periods`)
SHALL render whichever half is present.

#### Scenario: Weather renders above the widgets
- **WHEN** the home page renders on a wide viewport
- **THEN** the weather strip spans the full content width above the side-by-side news and events
  widgets; on a narrow viewport it appears above the stacked widgets

#### Scenario: Period names come from the API
- **WHEN** the endpoint returns first periods named "Tonight" and "Wednesday" (an evening visit)
- **THEN** the strip labels the forecast "Tonight" and "Wednesday", not "Today"

#### Scenario: Observation age is visible
- **WHEN** the endpoint returns current conditions observed 45 minutes ago
- **THEN** the strip shows the observation's "as of" time alongside the conditions

#### Scenario: Weather failure does not break the other widgets
- **WHEN** the weather request fails but the news and events requests succeed
- **THEN** the strip shows a one-line notice and both widgets render their content normally

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
render up to 5 upcoming events, soonest first, reusing the events feature's `EventCard`
component. A failed load SHALL show an error message inside the widget; an empty result SHALL
show an empty-state message.

#### Scenario: Saved event filters are ignored
- **WHEN** the user has topic and distance filters saved from the events page and opens `/`
- **THEN** the widget's request carries no filter parameters and shows the next 5 events
  regardless of those saved filters

#### Scenario: Next five upcoming events render
- **WHEN** the events endpoint returns events
- **THEN** the widget shows at most 5 event cards ordered by start time ascending

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
