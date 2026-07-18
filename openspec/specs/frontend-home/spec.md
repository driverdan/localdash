# frontend-home Specification

## Purpose

The landing page served at `/`: a widget grid composing at-a-glance digest widgets — latest
news beside a right column of weather above EPB outages above current events — all with
independent, unfiltered data fetches, and "view all" links into the full feature pages. A
feature namespace under `frontend/src/features/home/` that reuses the news card component
through its public surface and renders its own compact weather, outage, and events digests,
designed so future widgets are added as pure additions.
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
in the right column, a weather widget above an "Outages" widget above a "Current events"
widget. The news and events widgets SHALL each have a heading and a "view all" link that
navigates client-side (no full page load) to `/news` and `/events` respectively; the outages
widget's "view all" link navigates to `/map` the same way. The grid SHALL use an auto-fitting
column layout so future widgets can be added as pure additions without restructuring the page;
the weather, outages, and events widgets SHALL share a single grid item (a column container) so
they count as one column of the auto-fit layout.

#### Scenario: View-all links navigate client-side
- **WHEN** the user clicks the news widget's "view all" link
- **THEN** the URL becomes `/news` and the full news feed renders without a full page load

#### Scenario: Widgets lay out as a grid
- **WHEN** the home page renders on a wide viewport
- **THEN** the news widget appears beside a right column containing the weather widget above the
  outages widget above the events widget; on a narrow viewport the widgets stack in the order
  news, weather, outages, events

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

### Requirement: Current events digest widget
The events widget SHALL be titled "Current events" and fetch `GET /api/v1/events/items?limit=10`
with no topic, distance, or search parameters — ignoring any event filter preferences persisted
by the events feature — and render up to 10 events, soonest first, as abbreviated digest rows
owned by the home feature (not the events feature's `EventCard`). Each row SHALL show only: the
event title linked to the event's primary source URL (opening in a new tab; plain text when the
event has no links), and the full formatted date/time produced by the shared
`fmtEventDate(starts_at, ends_at)` formatter, followed by the distance in miles when
`distance_miles` is non-null. Rows SHALL NOT show tags, images, venue/address, descriptions, or a
source-link list. A failed load SHALL show an error message inside the widget; an empty result
SHALL show an empty-state message.

#### Scenario: Widget is titled "Current events"
- **WHEN** the home page renders the events digest widget
- **THEN** the widget heading reads "Current events"

#### Scenario: Saved event filters are ignored
- **WHEN** the user has topic and distance filters saved from the events page and opens `/`
- **THEN** the widget's request carries no filter parameters and shows the next 10 events
  regardless of those saved filters

#### Scenario: Next ten events render as abbreviated rows
- **WHEN** the events endpoint returns events
- **THEN** the widget shows at most 10 digest rows ordered by start time ascending, each showing
  only a linked title and a formatted date/time with distance — no tags, image, venue,
  description, or source-link list

#### Scenario: Title links to the primary source
- **WHEN** a digest row renders for an event whose first link has a source URL
- **THEN** the title is a link to that URL that opens in a new tab

#### Scenario: Distance is omitted when unknown
- **WHEN** a digest row renders for an event whose `distance_miles` is null
- **THEN** the row shows the formatted date/time with no distance fragment

#### Scenario: No events
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
stories digest, an `events` ping refetches the events digest, a `weather` ping refetches the
weather strip, and a `timeseries` diff whose `source` is `epb` refetches the outages digest
(diffs for other sources SHALL NOT trigger an outages refetch). The same loaders SHALL run on
bus reconnect. On-mount initial fetches and the per-widget loaded/error flags are unchanged — a
live refetch that fails leaves the previous widget content in place rather than blanking it.

#### Scenario: Digest updates without a reload
- **WHEN** the user is viewing `/` and a news refresh cycle completes server-side
- **THEN** the stories digest refetches and shows the new stories without a page reload or
  navigation

#### Scenario: Weather strip follows the weather ping
- **WHEN** a `{topic: "weather", type: "updated"}` message arrives
- **THEN** the weather strip refetches `/api/v1/weather/current` and renders the fresh conditions

#### Scenario: Outages digest follows epb timeseries diffs
- **WHEN** a `{topic: "timeseries", type: "diff", source: "epb"}` message arrives
- **THEN** the outages digest refetches and renders the updated summary

#### Scenario: Non-epb diffs do not refetch the outages digest
- **WHEN** a `{topic: "timeseries", type: "diff", source: "hc911"}` message arrives
- **THEN** the outages digest performs no refetch

#### Scenario: Failed live refetch keeps previous content
- **WHEN** a ping-triggered digest refetch fails
- **THEN** the widget keeps showing its previous content

### Requirement: Weather widget
The home page SHALL render a weather widget at the top of the widget grid's right column, above
the "Outages" and "Current events" widgets. The weather, outages, and events widgets SHALL be
wrapped in a single column container that is one grid item, so the grid's auto-fit behavior is
preserved (future top-level widgets remain pure additions). The weather widget SHALL use the shared widget visual language: a
widget header reading "Weather" (with no view-all link, as there is no weather page), current
conditions first, then the forecast periods stacked vertically as rows. It SHALL fetch
`GET /api/v1/weather/current` into home-owned state, in parallel with the other widgets' fetches,
and render current conditions (temperature, description, icon, and an "as of" time from the
observation timestamp, so a lagging station reading is not presented as live) plus the returned
forecast periods labeled with their NWS-assigned period names — never a hardcoded "Today". When
the payload carries a non-null `aqi`, the widget SHALL render it in the current-conditions area
as a compact chip showing the AQI value and category name, colored with the standard EPA AQI
category color for the payload's category number (1 green through 6 maroon) with legible text
contrast; when `aqi` is `null` the widget SHALL render nothing AQI-related. The AQI chip SHALL
render whenever `aqi` is present, including when `current` is `null`. A
failed load SHALL show a one-line notice inside the widget body and SHALL NOT affect the news or
events widgets; a partial response (missing `current` or empty `periods`) SHALL render whichever
half is present.

#### Scenario: Weather renders in the right column above events
- **WHEN** the home page renders on a wide viewport
- **THEN** the weather widget appears at the top of the right column, above the outages and
  events widgets, beside the news widget; on a narrow viewport the widgets stack in the order
  news, weather, outages, events

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

#### Scenario: AQI chip renders with its category color
- **WHEN** the endpoint returns `aqi` with value 62, category 2, and name "Moderate"
- **THEN** the widget shows a chip reading "AQI 62 · Moderate" colored with the EPA Moderate
  (yellow) category color

#### Scenario: No AQI, no chip
- **WHEN** the endpoint returns `aqi: null`
- **THEN** the widget renders current conditions and periods with no AQI chip and no empty
  placeholder

#### Scenario: AQI outlives a missing observation
- **WHEN** the endpoint returns `current: null` with a non-null `aqi`
- **THEN** the widget renders the AQI chip alongside the forecast periods

#### Scenario: Weather failure does not break the other widgets
- **WHEN** the weather request fails but the news and events requests succeed
- **THEN** the weather widget shows a one-line notice and both other widgets render their content
  normally

### Requirement: Outages digest widget
The home page SHALL render an "Outages" widget in the widget grid's right column, directly
beneath the weather widget and above the events widget, summarizing currently active EPB
outages. The widget SHALL compute its summary client-side from
`GET /api/v1/timeseries/entities?source=epb` (active entities only, the endpoint default): for
each service (`energy`, `fiber`) with at least one active outage, one row showing the outage
count with a human label ("power" for `energy`, "fiber" verbatim) and, when the summed
`customer_quantity` across that service's outages is greater than zero, the number of customers
affected (e.g. "3 power outages · 1,240 customers"). When no outages are active the widget
SHALL show a "No current outages" state (not an error). The widget SHALL have a "View all" link
that navigates client-side to `/map`.

The widget SHALL always render — it SHALL NOT consult source configuration or admin state
(e.g. `GET /api/v1/timeseries/sources`), and an empty active set renders the zero state
regardless of why it is empty. A failed entities load SHALL show an error message inside the
widget without affecting other widgets.

#### Scenario: Active outages summarize per service
- **WHEN** the entities endpoint returns three active `energy` outages totaling 1,240 customers
  and one active `fiber` outage totaling 89 customers
- **THEN** the widget shows a power row with count 3 and 1,240 customers and a fiber row with
  count 1 and 89 customers

#### Scenario: Customers fragment omitted when unknown
- **WHEN** a service's active outages carry no positive `customer_quantity` values
- **THEN** that service's row shows the outage count without a customers fragment

#### Scenario: No outages is a reassuring empty state
- **WHEN** the entities endpoint returns no active `epb` entities
- **THEN** the widget renders with a "No current outages" message, not an error and not hidden

#### Scenario: View-all navigates to the map
- **WHEN** the user clicks the outages widget's "view all" link
- **THEN** the URL becomes `/map` and the map renders without a full page load

#### Scenario: Outage failure does not break sibling widgets
- **WHEN** the entities request fails but the weather and events requests succeed
- **THEN** the outages widget shows an error message and the weather and events widgets render
  normally

