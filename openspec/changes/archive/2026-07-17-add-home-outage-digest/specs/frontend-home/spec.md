## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Widget grid landing page
The home page SHALL render a grid of widget cards: a "Latest news" widget in the left column and,
in the right column, a weather widget above an "Outages" widget above an "Upcoming events"
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
