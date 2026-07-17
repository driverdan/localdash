## ADDED Requirements

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

## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: Current weather strip
**Reason**: The full-width weather strip is replaced by a weather widget inside the grid's right
column; its data, rendering, and failure-isolation behavior move unchanged into the new "Weather
widget" requirement.
**Migration**: See the "Weather widget" requirement added by this change; no data or API
migration — the layout and visual treatment change only.
