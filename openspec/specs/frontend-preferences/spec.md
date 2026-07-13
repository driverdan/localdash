# frontend-preferences Specification

## Purpose

Client-side persistence of per-feature view preferences (`frontend/src/lib/prefs.svelte.ts`):
localStorage keys, serialization, tolerant loading, and the persist-on-change effect that the
`frontend-timeseries`, `frontend-events`, and `frontend-news` features build on. Per-browser only —
there is no server-side or per-account preference storage.

## Requirements

### Requirement: Per-feature localStorage persistence
The frontend SHALL persist per-feature view preferences in `localStorage` under one JSON key per
feature: `localdash.map` (selected sources, selected categories, show-closed toggle, closed
window), `localdash.events` (topics, max distance), and `localdash.news` (active tab, time window,
multi-source-only toggle). Preferences SHALL be written whenever any persisted field changes and
applied at feature-state initialization, before first render. Ephemeral state — search text,
status/jurisdiction dropdowns, open detail panel, fetched data, connection state — SHALL NOT be
persisted.

#### Scenario: Preferences survive a reload
- **WHEN** the user unchecks a map source, sets the news window to 24 h, and reloads the page
- **THEN** the map source remains unchecked and the news window remains 24 h

#### Scenario: Ephemeral state resets on reload
- **WHEN** the user types a search term on the map page and reloads
- **THEN** the search box is empty while the persisted filter selections are restored

### Requirement: Tolerant preference loading
Loading SHALL never break the app: a missing key, invalid JSON, or non-object value SHALL yield
defaults, and within a stored object each field SHALL be applied only if it passes a type check —
unknown or wrong-typed fields are ignored per-field, falling back to that field's default.
`localStorage` write failures (quota, unavailability) SHALL be swallowed; the app then runs with
in-memory state only.

#### Scenario: Corrupt stored value falls back to defaults
- **WHEN** `localdash.map` contains invalid JSON and the page loads
- **THEN** the map page initializes with default selections and does not error

#### Scenario: Wrong-typed field is ignored individually
- **WHEN** `localdash.news` contains `{"hours": "banana", "multiOnly": true}`
- **THEN** the time window uses its default while the multi-source-only toggle restores as on
