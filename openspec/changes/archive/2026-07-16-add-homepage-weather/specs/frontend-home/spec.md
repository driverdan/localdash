# frontend-home Specification (delta)

## ADDED Requirements

### Requirement: Current weather strip
The home page SHALL render a weather strip as the first item of the widget grid, spanning the
grid's full width (above the news and events widgets at every viewport size). The strip SHALL
fetch `GET /api/v1/weather/current` into home-owned state, in parallel with the other widgets'
fetches, and render current conditions (temperature, description, icon, and an "as of" time from
the observation timestamp, so a lagging station reading is not presented as live) plus the
returned forecast periods labeled with their NWS-assigned period names — never a hardcoded
"Today". A failed load SHALL collapse the strip to a one-line notice (no layout hole) and SHALL
NOT affect the news or events widgets; a partial response (missing `current` or empty `periods`)
SHALL render whichever half is present.

#### Scenario: Weather renders above the widgets
- **WHEN** the home page renders on a wide viewport
- **THEN** the weather strip spans the full grid width above the side-by-side news and events
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

## MODIFIED Requirements

### Requirement: Widget grid landing page
The home page SHALL render a grid of widget cards — a full-width weather strip first, then a
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
