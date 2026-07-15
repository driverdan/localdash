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
multi-source-only toggle). A feature MAY additionally persist ephemeral-but-restorable view state
under a namespaced key derived from its feature key (e.g. `localdash.map.view` for the map
viewport); such a key SHALL be written and read independently of the feature's persist-on-change
preference blob, so writing it never alters the semantics of the feature's main key. Preferences
SHALL be written whenever any persisted field changes and applied at feature-state initialization,
before first render. Ephemeral state — search text, status/jurisdiction dropdowns, open detail
panel, fetched data, connection state — SHALL NOT be persisted.

#### Scenario: Preferences survive a reload
- **WHEN** the user unchecks a map source, sets the news window to 24 h, and reloads the page
- **THEN** the map source remains unchecked and the news window remains 24 h

#### Scenario: Ephemeral state resets on reload
- **WHEN** the user types a search term on the map page and reloads
- **THEN** the search box is empty while the persisted filter selections are restored

#### Scenario: A namespaced view-state key does not affect the main preference key
- **WHEN** the user only pans the map (changing the `localdash.map.view` viewport) without touching any filter
- **THEN** the `localdash.map` filter blob is not written, so filtering keeps its all-on default behavior for sources added later

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

### Requirement: Map viewport persistence
The frontend SHALL persist the map viewport under the `localdash.map.view` key as a JSON object of
`{ zoom, lat, lng }` numbers, written when the map moves and read at map initialization. Loading
SHALL be all-or-nothing: if the key is missing, holds invalid JSON, or any of `zoom`, `lat`, `lng`
is absent or not a finite number, the map SHALL use its default view rather than a partially
restored one. Storage write failures (quota, unavailability) SHALL be swallowed, leaving the map on
in-memory viewport state.

#### Scenario: Round-trip through storage
- **WHEN** the map viewport is saved and the page reloads
- **THEN** the map reads `{ zoom, lat, lng }` back and restores that viewport

#### Scenario: Non-finite field discards the whole stored viewport
- **WHEN** `localdash.map.view` contains `{"zoom": 14, "lat": "banana", "lng": -85.3}`
- **THEN** the map opens at its default view and does not error

### Requirement: Reserved enumerable preference namespace
The `localdash.` prefix SHALL be a reserved namespace for **all** persisted browser preference state, and SHALL be enumerable so that a reader can list what is stored without knowing the key names in advance.

The namespace SHALL cover every key the frontend persists for a browser, including keys not written through this module's helpers — `localdash.theme` (written directly by the theme module, since theming must apply before first paint) and namespaced view-state keys such as `localdash.map.view`. Any future persisted preference key SHALL use the prefix. A key outside the prefix SHALL NOT be considered preference state and SHALL NOT be enumerated.

This module SHALL expose an enumeration function returning the `localdash.` keys currently present in `localStorage`. Enumeration SHALL report only keys that are actually stored; a key that has never been written SHALL simply be absent from the result, since key-absence is itself meaningful state (for `localdash.map`, an absent key means all categories on, including ones added later, whereas a present key is an allowlist).

Enumeration SHALL be tolerant, consistent with this module's other read paths: if `localStorage` is unavailable or throws, enumeration SHALL yield an empty result rather than propagating an error.

The namespace guarantee exists so shell code can inspect and clear preference state generically — reading the namespace crosses no isolation boundary, because the namespace is owned by this shell module rather than by any feature.

#### Scenario: Enumerates only stored namespace keys
- **WHEN** `localdash.map` and `localdash.theme` are stored, `localdash.news` has never been written, and an unrelated key `other.thing` is stored
- **THEN** enumeration returns `localdash.map` and `localdash.theme`, omitting both `localdash.news` and `other.thing`

#### Scenario: Covers keys not written through the prefs helpers
- **WHEN** the theme module has written `localdash.theme` and the map has written `localdash.map.view`, neither via this module's persist-on-change effect
- **THEN** enumeration includes both keys

#### Scenario: Storage unavailability yields an empty result
- **WHEN** `localStorage` access throws (private mode or storage disabled) and enumeration runs
- **THEN** it returns an empty result and does not error

