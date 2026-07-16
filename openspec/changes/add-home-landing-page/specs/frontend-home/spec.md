## ADDED Requirements

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
The home page SHALL render a grid of widget cards, initially two: a "Latest news" widget and an
"Upcoming events" widget. Each widget SHALL have a heading and a "view all" link that navigates
client-side (no full page load) to `/news` and `/events` respectively. The grid SHALL use an
auto-fitting column layout so future widgets (weather, timeseries summary) can be added as pure
additions without restructuring the page.

#### Scenario: View-all links navigate client-side
- **WHEN** the user clicks the news widget's "view all" link
- **THEN** the URL becomes `/news` and the full news feed renders without a full page load

#### Scenario: Widgets lay out as a grid
- **WHEN** the home page renders on a wide viewport
- **THEN** the news and events widgets appear side by side; on a narrow viewport they stack

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
