# frontend-debug Specification

## Purpose

A shell-owned debug overlay for investigating issues and inspecting live UI state in-app: a persistent
π toggle button and a route-aware modal, backed by a singleton reactive debug store in
`frontend/src/lib/`. Feature-agnostic shell code (like the nav, status bar, and theme switcher), it
lets features publish runtime state to a shared store without cross-feature imports. Ships with the
map section (live zoom + center); structured so new sections can be added without touching existing
ones.

## Requirements

### Requirement: Debug overlay toggle button
The shell SHALL render a persistent debug toggle button on every route, drawn as the **π** glyph in a
small styled button. The button SHALL be feature-agnostic shell code (`frontend/src/lib/` +
`App.svelte`), consistent with the shell's ownership of the nav, status bar, and theme switcher, and
SHALL NOT depend on any feature. Its styling SHALL be theme-aware (a visible variant in both the
default and dark themes). On desktop-width viewports the button SHALL float fixed in the bottom-right
corner of the screen; on mobile-width viewports (a defined breakpoint) it SHALL instead sit at the
bottom of the page. Clicking the button SHALL toggle the debug modal open and closed.

#### Scenario: Button present on every route
- **WHEN** the user is on any route (`/`, `/map`, or `/events`)
- **THEN** the π debug toggle button is visible

#### Scenario: Desktop position
- **WHEN** the viewport is at desktop width
- **THEN** the π button is fixed in the bottom-right corner of the screen

#### Scenario: Mobile position
- **WHEN** the viewport is below the mobile breakpoint
- **THEN** the π button is positioned at the bottom of the page rather than floating bottom-right

#### Scenario: Toggle opens and closes the modal
- **WHEN** the user clicks the π button while the debug modal is closed
- **THEN** the modal opens; clicking the button again (or the modal's close control) closes it

### Requirement: Debug modal placement
The debug modal SHALL be anchored to the top-right of the main body when open, offset from the
timeseries incident detail panel so that both can be open at the same time without overlapping. The
modal SHALL be theme-aware and SHALL provide a close control.

#### Scenario: Modal opens top-right of the main body
- **WHEN** the debug modal is opened
- **THEN** it appears anchored to the top-right of the main body

#### Scenario: Coexists with the incident detail panel
- **WHEN** an incident detail panel is open on the `/map` route and the user opens the debug modal
- **THEN** both panels are visible at once and neither overlaps the other

### Requirement: Route-aware debug sections
The debug modal SHALL render sections relevant to the current route, alongside shell sections that are present on every route. It SHALL be built as a general
shell that composes always-present sections and route-specific sections, backed by a singleton reactive debug store in
`frontend/src/lib/` (mirroring the timeseries store pattern), so new sections can be added without
changing existing ones. Route-specific content comes from two sources: sections the shell renders for
known routes (e.g. the map section), and feature debug actions registered into the store by the
mounted feature. On routes with neither an applicable route-specific shell section nor any registered feature action
the modal SHALL show a neutral placeholder in place of the route-specific content, indicating that the current view publishes no debug
data. Because the Settings section is always present, the modal SHALL never be entirely empty, and the placeholder SHALL
scope to the route-specific content rather than to the modal as a whole.

#### Scenario: Map route shows the map section
- **WHEN** the debug modal is open on the `/map` route
- **THEN** it renders the map debug section

#### Scenario: Route with a registered action shows it instead of the placeholder
- **WHEN** the debug modal is open on a route whose mounted feature has registered a debug action (e.g. `/` or `/events`)
- **THEN** it renders that action rather than the "no debug data for this view" placeholder

#### Scenario: Route with no section or action shows a placeholder beside the always-present sections
- **WHEN** the debug modal is open on a route with no route-specific shell section and no registered feature action
- **THEN** it shows a neutral "no debug data for this view" placeholder for the route-specific content, while the
  always-present Settings section still renders

### Requirement: Feature debug action registry
The shell debug store SHALL expose a registry of feature-provided debug actions, and a feature SHALL be able to register and unregister an action without the shell importing any feature code (preserving the `lib/`-imports-no-feature rule). This mirrors the map-viewport pattern: the feature WRITES to the shared store, the shell READS it. Each registered action SHALL provide a stable id, a display label, an invoke callback, and reactive `disabled` and `status` values (exposed as getters so the panel reflects live feature state — e.g. disabling while an operation is in flight and updating status text — without capturing stale snapshots). A feature SHALL register its action when it mounts and unregister it when it tears down, so an action is present only while its owning feature is on screen; unregistering SHALL be idempotent.

#### Scenario: Feature registers and unregisters an action
- **WHEN** a feature mounts and registers a debug action, then later tears down and unregisters it
- **THEN** the action is present in the debug store's registry while the feature is mounted and absent after teardown, and no feature module is imported by `frontend/src/lib/`

#### Scenario: Action state stays live
- **WHEN** a registered action's owning feature flips its reactive `disabled` or `status` state (e.g. an in-flight refresh)
- **THEN** the value read through the registered action's getters reflects the new state without re-registration

### Requirement: Debug panel renders registered feature actions
The debug modal SHALL render each registered feature action as a control in a debug section: a button showing the action's label that invokes its callback when clicked, disabled while the action's reactive `disabled` is true, accompanied by the action's status text shown when non-empty (and hidden when empty). Because actions are unregistered on feature teardown, the panel SHALL show only the current route's actions. Styling SHALL follow the global styling contract (semantic classes in the global debug stylesheet, theme-aware, no scoped `<style>` blocks).

#### Scenario: Registered action renders as a button
- **WHEN** the debug modal is open on a route whose feature has registered a refresh action
- **THEN** the modal shows a button with the action's label that runs the action's callback on click

#### Scenario: Button reflects disabled and status
- **WHEN** the user clicks a registered action's button and the action sets its reactive `disabled` and status text while running
- **THEN** the button is disabled for the duration and the action's status text is displayed, and the status is hidden again once it returns to empty

### Requirement: Map debug section
On the `/map` route the debug modal SHALL display the map's current **zoom level** and the
**latitude and longitude of the map center**, read from the shell debug store. These values SHALL
update live as the user pans and zooms the map.

#### Scenario: Shows current zoom and center
- **WHEN** the debug modal is open on `/map`
- **THEN** it displays the map's current zoom level and the lat/lng of the map center

#### Scenario: Updates as the map moves
- **WHEN** the user pans or zooms the map while the debug modal is open
- **THEN** the displayed zoom level and center coordinates update to match the new viewport

### Requirement: Stored settings debug section
The debug modal SHALL render a **Settings** section on every route, listing the browser's stored LocalDash preference keys. The section SHALL be always-present shell code and SHALL NOT be route-gated: preferences are global browser state, so a key SHALL be inspectable from any route regardless of which feature owns it.

The section SHALL discover keys by enumerating the reserved `localdash.` namespace in `localStorage` (see the `frontend-preferences` enumeration requirement), NOT by a registry that features write to. It SHALL therefore require no feature imports, preserving the `lib/`-imports-no-feature rule, and a preference key introduced by a future feature SHALL appear with no registration step.

The section SHALL list exactly the keys that are present in storage, showing each key's **stored value** rather than the feature's in-memory state. Absence SHALL be conveyed by omission from the list. Displaying stored values is required because they routinely disagree with in-memory state — the persist-on-change effect deliberately does not write on first run, so a visitor who never changed a preference has defaults in memory and no key on disk, and for `localdash.map` that absence is load-bearing (an absent key means all categories on, including ones added later; a present key is an allowlist).

Value rendering SHALL be tolerant and SHALL NOT error on any stored content: a JSON object SHALL be shown in a readable expanded form, and a value that is not a JSON object — a bare string such as `localdash.theme`, or corrupt/unparseable content — SHALL be shown as its raw stored text.

When no `localdash.` key is present at all, the section SHALL show an explicit empty state rather than hiding itself, because "no settings are saved" is a meaningful answer.

#### Scenario: Section present on every route
- **WHEN** the debug modal is open on any route (`/`, `/map`, `/events`, or an unknown route)
- **THEN** the Settings section is rendered, listing the stored `localdash.` keys

#### Scenario: A feature's key is visible from another route
- **WHEN** `localdash.news` is stored and the debug modal is opened on `/map`
- **THEN** the Settings section lists `localdash.news` with its stored value

#### Scenario: Stored value is shown, not in-memory state
- **WHEN** the user has never changed a news preference, so no `localdash.news` key exists, and the debug modal is opened
- **THEN** `localdash.news` is absent from the list rather than shown with the in-memory default values

#### Scenario: Non-object and corrupt values render as raw text
- **WHEN** `localdash.theme` holds the bare string `dark` and another `localdash.` key holds invalid JSON
- **THEN** both are listed showing their raw stored text, and the section does not error

#### Scenario: Empty state when nothing is stored
- **WHEN** the debug modal is opened in a browser with no `localdash.` key stored
- **THEN** the Settings section renders an explicit empty state indicating no settings are saved

### Requirement: Per-key settings deletion
Each listed key SHALL have its own delete control that removes **only that key** from `localStorage`. There SHALL be no delete-all control.

Deleting SHALL NOT reload the page and SHALL NOT reset the owning feature's in-memory state. Because in-memory state is untouched, deleting SHALL have no immediately visible effect on the app, and the affected feature's next change to any persisted field SHALL re-save its blob, restoring the key with the pre-delete values. To keep this honest, a deleted row SHALL remain visible in the section and SHALL show a **reload to apply** notice, so the user is told that the deletion takes effect only on reload and that it can be undone by continued interaction before then.

Deletion SHALL tolerate `localStorage` write failures without erroring, consistent with the preferences module's swallow-on-failure contract.

#### Scenario: Delete removes only the targeted key
- **WHEN** `localdash.map` and `localdash.news` are both stored and the user clicks delete on the `localdash.map` row
- **THEN** `localdash.map` is removed from `localStorage` and `localdash.news` remains stored

#### Scenario: Delete does not reload or change the app
- **WHEN** the user deletes `localdash.news` while the news feed is showing a restored non-default tab
- **THEN** the page does not reload and the feed continues showing that tab

#### Scenario: Deleted row shows the reload notice
- **WHEN** the user deletes a key
- **THEN** that row remains visible in the section and shows a "reload to apply" notice

#### Scenario: Deletion takes effect on reload
- **WHEN** the user deletes `localdash.map` and reloads the page without touching any map filter in between
- **THEN** the map initializes from defaults with all categories on, including categories added since the key was written

### Requirement: Settings snapshot read model
The Settings section SHALL read `localStorage` when the debug modal opens, and SHALL update its own view when the user deletes a key. It SHALL NOT poll storage and SHALL NOT subscribe to the `storage` event.

This snapshot model is required because same-tab writes fire no `storage` event (that event notifies other tabs only), so a key rewritten by the current tab — for example a map pan rewriting `localdash.map.view` seconds after a delete — cannot be observed live. Re-reading on open SHALL therefore be the mechanism by which a resurrected key surfaces: reopening the modal SHALL show the key present again with its current stored value and no pending reload notice, truthfully reflecting that the deletion was undone.

#### Scenario: Snapshot refreshes on reopen
- **WHEN** the user deletes `localdash.map.view`, closes the debug modal, pans the map (which rewrites the key), and reopens the modal
- **THEN** `localdash.map.view` is listed again with its new stored value and no reload notice

#### Scenario: Values are not live while open
- **WHEN** the debug modal is open and a stored key's value changes in the current tab
- **THEN** the displayed value remains the one read when the modal opened, and no error occurs

