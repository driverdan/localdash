## ADDED Requirements

### Requirement: Configurable site name

The system SHALL read a single user-facing site name from the `SITE_NAME` environment variable at
process start, exposed as an application setting, defaulting to `LocalDash` when unset. This value
SHALL be the sole source of truth for the site name shown to users. The FastAPI application title
SHALL derive from this setting rather than a hardcoded string.

#### Scenario: Default when unset

- **WHEN** the application starts with no `SITE_NAME` in the environment
- **THEN** the site name resolves to `LocalDash` and the FastAPI application title is `LocalDash`

#### Scenario: Overridden at run time

- **WHEN** the application starts with `SITE_NAME` set to `Chattanooga LocalDash`
- **THEN** the site name resolves to `Chattanooga LocalDash` and the FastAPI application title is
  `Chattanooga LocalDash`, with no frontend rebuild required

### Requirement: Runtime site-name injection into served index.html

Whenever the static mount serves `index.html` — both for `GET /` and for the SPA fallback of a
client-side route — the system SHALL inject the configured site name into the served HTML so it is
correct at first paint without a frontend rebuild. The injection SHALL set the document `<title>`
to the configured name and SHALL expose the name synchronously to the app bundle as a
`window.__SITE_NAME__` global before the bundle loads. Injection SHALL operate on placeholder
tokens carried in the built `index.html`, leaving all other markup (including the theme bootstrap
script) unchanged.

#### Scenario: Title reflects the configured name

- **WHEN** the application runs with `SITE_NAME` set to `Acme Dashboard` and a browser requests
  `GET /`
- **THEN** the served `index.html` has `<title>Acme Dashboard</title>` and defines
  `window.__SITE_NAME__` equal to `Acme Dashboard` before the app bundle script

#### Scenario: Injection also applies on SPA deep links

- **WHEN** the application runs with `SITE_NAME` set to `Acme Dashboard` and a browser requests a
  client route such as `GET /map`
- **THEN** the fallback response is `index.html` with the same title and `window.__SITE_NAME__`
  injection applied

#### Scenario: Non-index responses are unaffected

- **WHEN** a client requests a built asset (e.g. `GET /assets/app.js`) or any `/api/...` path
- **THEN** no site-name injection occurs and the response is unchanged from before
