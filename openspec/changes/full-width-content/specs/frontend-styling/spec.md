## ADDED Requirements

### Requirement: Full-width main content regions
Each route's main content region SHALL span the full width of the page. Per-feature stylesheets
SHALL NOT constrain a route's primary content container with a `max-width` cap or center it with
auto horizontal margins; the container SHALL fill the width its route region provides, leaving
only the sheet's declared horizontal padding between the content and the viewport edges. This
applies to the home widget grid's scroll container and to the news and events feed and sources
regions, matching the map route, whose layout already fills the page. Content-level sizing that
is not a page-width cap — a sidebar's fixed track, a form control's width, an image's
`max-height` — is unaffected.

#### Scenario: Feed content fills a wide viewport
- **WHEN** the news or events page is viewed at a viewport wider than the former 46rem cap
- **THEN** the feed's cards extend across the full page width, inset only by the region's
  horizontal padding, with no centered empty gutter on either side

#### Scenario: Home widget grid fills a wide viewport
- **WHEN** the home page is viewed at a viewport wider than the former 74rem cap
- **THEN** the widget grid's scroll container stretches across the full page width, and its
  widgets divide that full width between them

#### Scenario: No page-width caps remain in the feature stylesheets
- **WHEN** the per-feature stylesheets are inspected for the rules governing the home, news, and
  events content regions
- **THEN** none of those rules declares a `max-width` page cap or `margin: 0 auto` centering, and
  no comment describes a cap that is no longer applied
