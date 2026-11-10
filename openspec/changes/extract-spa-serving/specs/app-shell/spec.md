## ADDED Requirements

### Requirement: Static mount revalidation and non-HTTP requests

Every HTTP response from the `/` static mount SHALL carry `Cache-Control: no-cache`. This covers
built assets, `index.html` served for `GET /`, and the SPA-fallback `index.html`. Browsers then
revalidate on every load: an unchanged file still gets a cheap conditional response, and a
redeploy's new bundle is picked up without a hard refresh, because the build's `index.html` is not
content-hashed. When a WebSocket upgrade reaches the static mount because no API route matched
it, the mount SHALL close it cleanly rather than raise. An example is an old bundle retrying a
removed endpoint.

#### Scenario: Index is served with no-cache

- **WHEN** a browser requests `GET /`
- **THEN** the response is the site-name-injected `index.html` with `Cache-Control: no-cache`

#### Scenario: SPA fallback is served with no-cache

- **WHEN** a browser requests a client route such as `GET /map`
- **THEN** the fallback `index.html` response carries `Cache-Control: no-cache`

#### Scenario: Built assets are served with no-cache

- **WHEN** a browser requests a built file that exists, such as `GET /assets/app.js`
- **THEN** the file is served unchanged with `Cache-Control: no-cache`

#### Scenario: Stray WebSocket upgrade is closed

- **WHEN** a client opens a WebSocket on a path that no API route accepts, such as
  `/api/v1/timeseries/ws`
- **THEN** the connection is closed without being accepted, and the server logs no traceback
