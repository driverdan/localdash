## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Route-aware debug sections
The debug modal SHALL render sections relevant to the current route. It SHALL be built as a general
shell that composes route-specific sections, backed by a singleton reactive debug store in
`frontend/src/lib/` (mirroring the timeseries store pattern), so new sections can be added without
changing existing ones. Route-specific content comes from two sources: sections the shell renders for
known routes (e.g. the map section), and feature debug actions registered into the store by the
mounted feature. On routes with neither an applicable shell section nor any registered feature action
the modal SHALL show a neutral placeholder rather than being empty or erroring.

#### Scenario: Map route shows the map section
- **WHEN** the debug modal is open on the `/map` route
- **THEN** it renders the map debug section

#### Scenario: Route with a registered action shows it instead of the placeholder
- **WHEN** the debug modal is open on a route whose mounted feature has registered a debug action (e.g. `/` or `/events`)
- **THEN** it renders that action rather than the "no debug data for this view" placeholder

#### Scenario: Route with no section or action shows a placeholder
- **WHEN** the debug modal is open on a route with no shell section and no registered feature action
- **THEN** it shows a neutral "no debug data for this view" placeholder instead of an empty or broken
  panel
