## MODIFIED Requirements

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
