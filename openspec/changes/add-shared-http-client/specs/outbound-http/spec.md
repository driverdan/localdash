## ADDED Requirements

### Requirement: Outbound HTTP clients come from one factory
Every `httpx` client the application uses to call an upstream service SHALL be constructed by the
factory in `app/http.py`. The factory SHALL require each caller to state its timeout and whether
redirects are followed; neither SHALL have a default. The User-Agent SHALL default to the
application's `user_agent` setting, read when the client is built; a caller SHALL pass a
User-Agent only to override that default with a different one. Every client SHALL send a non-empty
User-Agent: the factory SHALL offer no way to send httpx's own default (`python-httpx/<version>`),
and SHALL reject a blank override with an error. The `user_agent` setting SHALL be the only
setting the factory reads; every other value comes from the caller. The `user_agent` setting
SHALL default to `DEFAULT_USER_AGENT`, defined in `app/http.py` as `BROWSER_USER_AGENT` followed by
a space and `LocalDash/0.1` (a real browser string that still names the app), and SHALL remain
overridable through the environment (`USER_AGENT`). The `user_agent` and
`events_geocoder_user_agent` settings SHALL reject blank values when settings load. Requests made
through `feedparser` (news RSS feeds) are outside the factory's scope, but SHALL use the same
browser User-Agent constant (see "One shared browser User-Agent").

#### Scenario: No direct client construction outside the factory
- **WHEN** the application package `app/` is searched for `httpx.AsyncClient(`
- **THEN** the only match is inside `app/http.py`

#### Scenario: A call site states its request settings
- **WHEN** a collector, event source, geocoder, news fetcher or weather service obtains a client
- **THEN** its timeout and redirect policy are passed explicitly at that call, and a User-Agent is
  passed only when the site overrides the default (the browser User-Agent or the geocoder's own
  setting)

#### Scenario: A client built without a User-Agent sends the app's
- **WHEN** a client is built without a User-Agent argument
- **THEN** its requests carry the configured `user_agent` setting

#### Scenario: The default User-Agent is a browser string naming the app
- **WHEN** the `user_agent` setting is not overridden
- **THEN** its value is `Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0 LocalDash/0.1`: it starts with `BROWSER_USER_AGENT` and ends with
  `LocalDash/0.1`

#### Scenario: A blank User-Agent is rejected
- **WHEN** a caller passes an empty or whitespace-only User-Agent to the factory, or the
  `user_agent` or `events_geocoder_user_agent` setting is configured blank
- **THEN** an error is raised and no request is sent

### Requirement: Per-upstream request settings are preserved
Each upstream fetch SHALL send the User-Agent, use the timeout, apply the redirect policy and carry
the site-specific headers listed below. A change to any of these is a wire change and SHALL be made
deliberately, by updating this requirement.

| Fetch | User-Agent | Timeout (s) | Redirects followed |
|---|---|---|---|
| hc911, TDOT, EPB, TN American Water collectors | `user_agent` setting | 30 | no |
| Nominatim geocoder | `events_geocoder_user_agent` setting | 10 | no |
| Chattanooga Zoo source | `user_agent` setting | 20 | yes |
| Meetup source | `user_agent` setting | 20 | no |
| iCal source | `user_agent` setting | 20 | yes |
| Events Calendar (tribe) source | `user_agent` setting | 30 | yes |
| CitySpark source | `user_agent` setting | 30 | no |
| CarCruiseFinder source | browser User-Agent | 20 | yes |
| News `kind: html` listing scrape | browser User-Agent | 30 | yes |
| NWS / AirNow (weather) | `user_agent` setting | 10 | yes |

Site-specific headers SHALL also be preserved: hc911 sends `Content-Type: application/json`,
`X-Frontend-Auth` and `Origin`; TDOT sends `X-API-Key`; EPB and TN American Water send
`Accept: application/json`; Meetup sends a bearer `Authorization` and
`Content-Type: application/json`; weather sends `Accept: application/geo+json`.

#### Scenario: Request settings are pinned by a test
- **WHEN** the test suite runs each fetch listed above against a mock transport
- **THEN** each request's User-Agent, timeout and site-specific headers match the table, and a
  redirect response is followed exactly by the fetches marked "yes"

#### Scenario: No fetch sends httpx's default or an empty User-Agent
- **WHEN** any fetch listed above is made
- **THEN** its `User-Agent` header is non-empty and is not httpx's default
  (`python-httpx/<version>`); the Meetup, iCal, tribe and CitySpark sources send the `user_agent`
  setting

### Requirement: One shared browser User-Agent
The application SHALL define the mainstream browser User-Agent string exactly once, as
`BROWSER_USER_AGENT` in `app/http.py`. `DEFAULT_USER_AGENT` SHALL be built from that constant, not
from a second copy of the string. The news RSS fetch (via feedparser), the news HTML scrape,
and the CarCruiseFinder source SHALL all use that constant.

#### Scenario: News feeds and CarCruiseFinder share one constant
- **WHEN** a news RSS feed is fetched, a news `kind: html` listing is scraped, or CarCruiseFinder's
  listing is fetched
- **THEN** the request's User-Agent is `app.http.BROWSER_USER_AGENT`

#### Scenario: The string is not duplicated
- **WHEN** the application package is searched for the browser User-Agent string literal
- **THEN** it appears only in `app/http.py`

### Requirement: The geocoder reuses one client per refresh cycle
The Nominatim geocoder SHALL hold a single HTTP client for its lifetime, opened and closed by using
the geocoder as an async context manager. An events refresh cycle SHALL open one geocoder and share
it between source ingest and the geocode-failure retry pass. Calling `geocode` outside that context
SHALL raise an error rather than opening a client implicitly. Request spacing (at least
`events_geocoder_min_interval_seconds` between sends), the request's URL, query and headers, and
the "first query variant with a result wins" fallback SHALL be unchanged.

#### Scenario: Several lookups share one client
- **WHEN** a geocoder context performs several lookups
- **THEN** every request goes through the same client, and that client is closed when the context
  exits

#### Scenario: Spacing is unchanged with a shared client
- **WHEN** two lookups are issued back to back with `min_interval` set
- **THEN** the second request is sent no sooner than `min_interval` after the first

#### Scenario: Use outside the context fails fast
- **WHEN** `geocode` is called on a geocoder that has not been entered
- **THEN** it raises an error and sends no request

### Requirement: Tests substitute the transport and never reach the network
`app/http.py` SHALL expose a transport override that the test suite sets to route every
factory-built client through a mock transport. Production code SHALL NOT set it. The test suite
SHALL provide one shared fixture for installing a mock handler and recording the requests sent. By
default, every test SHALL run with a transport that refuses outbound requests, and a test that
sends any unmocked outbound request SHALL fail, even when the application code under test catches
the resulting error.

#### Scenario: A test mocks an upstream
- **WHEN** a test installs a handler through the shared fixture and calls code that fetches
- **THEN** the request reaches the handler, and the test can inspect the recorded request's URL,
  headers and timeout

#### Scenario: An unmocked request fails the test
- **WHEN** a test runs code that sends an outbound request without installing a mock
- **THEN** the test fails and names the requested URL, even when the caller swallowed the error
  (for example per-source isolation in an events or news refresh)
