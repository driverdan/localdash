## ADDED Requirements

### Requirement: SPA fallback for client-side routes
The static mount SHALL serve the SPA's `index.html` for any non-`/api` request path that does not
match a built file and has no file extension, so client-side routes (e.g. `/map`) deep-link and
survive a page reload. Requests for missing asset paths (paths with a file extension) SHALL still
return 404, and `/api/...` paths SHALL never reach the fallback.

#### Scenario: Deep link to a client route
- **WHEN** a browser requests `GET /map` directly
- **THEN** the response is `index.html` and the SPA renders the map route

#### Scenario: Missing assets still fail loudly
- **WHEN** a client requests `GET /assets/nonexistent.js`
- **THEN** the response is 404, not `index.html`

#### Scenario: API paths never fall back
- **WHEN** a client requests an unknown `/api/...` path
- **THEN** the API's own 404 is returned, not `index.html`
