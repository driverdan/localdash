## MODIFIED Requirements

### Requirement: Site footer with open-source attribution
The shell SHALL provide a shared site footer component (in `frontend/src/lib/`) containing a
single link with the text "100% Open Source" pointing at
`https://github.com/driverdan/localdash`, opening in a new tab so in-app state (including the
live WebSocket connection) is preserved. The footer SHALL be rendered in the flow of the
scrollable content — as the last element inside the route's scroll region — on every route: the
home, news, and events routes render it at the end of their content region, and the map route
renders it at the end of its sidebar scroll region, after the incident table. On every route it
appears after the content rather than as a fixed always-visible strip, and it SHALL receive no
route-specific positioning treatment (no pinning, no sticky positioning, no bottom-alignment
spacing) — it simply flows wherever the content ends. The footer SHALL be styled via the global
stylesheet using existing design tokens only, so all themes inherit it without per-theme rules.

#### Scenario: Footer reached by scrolling content routes
- **WHEN** the user scrolls to the bottom of the content on the home, news, or events route
- **THEN** a site footer appears after the route's content containing a "100% Open Source" link
  to `https://github.com/driverdan/localdash`

#### Scenario: Footer is not fixed
- **WHEN** a route's content overflows its scroll region and the user has not scrolled to the
  bottom
- **THEN** the site footer is not visible on screen (it flows after the content rather than
  being pinned to the viewport)

#### Scenario: Link preserves the running app
- **WHEN** the user activates the "100% Open Source" link
- **THEN** the repository page opens in a new tab and the dashboard keeps running (the live
  WebSocket connection is not torn down)

#### Scenario: Map route renders the footer at the end of the sidebar
- **WHEN** the user visits `/map` and scrolls the sidebar to the bottom of its content
- **THEN** the site footer appears after the incident table, inside the sidebar's scroll region,
  with the same "100% Open Source" link

#### Scenario: Map footer is not bottom-anchored when the sidebar is short
- **WHEN** the map route's sidebar content is shorter than the sidebar's height (so the sidebar
  does not scroll)
- **THEN** the site footer sits directly after the incident table with empty space below it,
  rather than being pushed to the sidebar's bottom edge

#### Scenario: Map pane itself has no footer
- **WHEN** the user visits `/map`
- **THEN** no site footer is rendered over or below the map pane; the footer appears only within
  the sidebar
