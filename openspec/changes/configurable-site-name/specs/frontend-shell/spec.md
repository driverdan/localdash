## ADDED Requirements

### Requirement: Site name is displayed from runtime configuration

The shell SHALL display the site name from the runtime-configured value rather than any hardcoded
string, consistently across the surfaces where the name appears. The built `index.html` SHALL carry
placeholder tokens (for the `<title>` and for a synchronous `window.__SITE_NAME__` assignment) that
the backend replaces at serve time; the header `<h1>` SHALL render the value read synchronously from
`window.__SITE_NAME__`, so it is correct at first paint with no additional network request and no
flash of a placeholder value. The previously hardcoded `Chattanooga ` prefix and ` (beta)` suffix
SHALL NOT be applied by the shell — the displayed name is exactly the configured value.

#### Scenario: Header shows the configured name

- **WHEN** the app loads and the backend has injected `window.__SITE_NAME__` as `Acme Dashboard`
- **THEN** the header `<h1>` renders `Acme Dashboard`, matching the browser tab title, with no
  additional fetch for the name

#### Scenario: No hardcoded qualifiers

- **WHEN** the configured site name is `LocalDash`
- **THEN** the header renders exactly `LocalDash` (not `Chattanooga LocalDash (beta)`)

#### Scenario: Placeholders present in built output for injection

- **WHEN** `vite build` has produced `static/index.html`
- **THEN** the built file contains the placeholder tokens the backend substitutes for the title and
  the `window.__SITE_NAME__` global, so serve-time injection has a defined target
