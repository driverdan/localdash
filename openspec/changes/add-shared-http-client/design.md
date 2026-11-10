## Context

`grep -rn "httpx.AsyncClient(" app` finds 13 constructions on `main`. Each one is a separate
decision about User-Agent, timeout and redirects, and the reason for each decision lives either in a
docstring or in AGENTS.md's "don't regress" sections. Several of those reasons come from upstreams
punishing a wrong User-Agent: TownNews returns 429, CarCruiseFinder returns 403, and NWS asks for an
identifying UA. Nothing in the test suite checks what goes out on the wire. The four geo collectors,
Meetup, iCal and the news HTML scrape have no fetch tests. The sources that do have fetch tests
patch `httpx.AsyncClient` by dotted path, with a separate copy of the helper in each test module:

- `tests/test_events_cityspark.py:230`, `tests/test_events_carcruisefinder.py:108`,
  `tests/test_events_tribe.py:156`: `install_transport`
- `tests/test_events_chattzoo.py:237`/`:285`: `_client_transport` + `_patch_client`. This one also
  pins the source's `_now` clock.
- `tests/test_events_geocoding.py:17` and `:100`: two variants in one file
- `tests/test_weather.py`: sets `WeatherService._transport`, the only seam built into app code

### Current request settings per call site (must be preserved)

"httpx default" for User-Agent means no override: httpx sends `python-httpx/<version>`. "Not
followed" for redirects means httpx's default `follow_redirects=False`.

| Call site | User-Agent | Timeout (s) | Redirects | Other headers |
|---|---|---|---|---|
| `app/collectors/hc911.py:52` `HC911Collector.fetch` | `settings.user_agent` (per-request) | 30 | not followed | `Content-Type: application/json`, `X-Frontend-Auth`, `Origin` |
| `app/collectors/tdot.py:83` `TdotCollector.fetch` | `settings.user_agent` (per-request) | 30 | not followed | `X-API-Key` |
| `app/collectors/epb.py:49` `EpbCollector.fetch` | `settings.user_agent` (per-request) | 30 | not followed | `Accept: application/json` |
| `app/collectors/tnaw.py:66` `TnawCollector.fetch` | `settings.user_agent` (per-request) | 30 | not followed | `Accept: application/json` |
| `app/events/geocoding.py:100` `NominatimGeocoder.geocode` | `events_geocoder_user_agent` (per-request) | 10 (ctor default) | not followed | none. **One client per query** |
| `app/events/sources/chattzoo.py:263` `ChattZooSource.fetch` | `settings.user_agent` via ctor (client header; ctor default repeats `"LocalDash/0.1"`) | 20 | followed | none |
| `app/events/sources/meetup.py:129` `MeetupSource.fetch` | httpx default | 20 | not followed | `Authorization: Bearer …`, `Content-Type: application/json` |
| `app/events/sources/ical.py:71` `ICalSource.fetch` | httpx default | 20 | followed | none |
| `app/events/sources/tribe.py:135` `TribeEventsSource.fetch` | httpx default (docstring: verified accepted) | 30 | followed | none |
| `app/events/sources/cityspark.py:231` `CitySparkSource.fetch` | httpx default (docstring: no browser UA needed) | 30 | not followed | none |
| `app/events/sources/carcruisefinder.py:153` `CarCruiseFinderSource.fetch` | `BROWSER_UA` (per-request) | 20 | followed | none |
| `app/news/fetcher.py:150` `_fetch_html` | `registry.USER_AGENT` (client header) | 30 | followed | none |
| `app/weather/service.py:115` `WeatherService._make_client` | `settings.user_agent` (client header) | 10.0 | followed | `Accept: application/geo+json` |
| `app/news/fetcher.py:91` `_parse_feed` (**feedparser/urllib, not httpx**) | `registry.USER_AGENT` via `agent=` | feedparser's | urllib's | `Accept: application/rss+xml, application/xml, */*` |

Every row keeps its User-Agent, timeout, redirect policy and other headers after this change. The
one exception is the geocoder's client lifetime (Decision 5). `_parse_feed` stays on feedparser
(AGENTS.md explains why). Only the constant it imports moves.

### Sibling changes (proposed in parallel; suggested landing order)

This change is #2 of 13. It overlaps with:

- **#1 `ingest-owns-entity-status`**: touches `normalize()` in the same collector files. The two
  only overlap textually: this change edits `fetch()` and that one edits `normalize()`.
- **#3 `move-timeseries-into-package`**: moves `app/collectors/` into `app/timeseries/`. It lands
  after this change and carries the edited collectors and their new fetch tests with it, so their
  import paths need updating there. `app/http.py` is feature-agnostic and stays at the top level.
- **#4 `unify-refresh-orchestration`**: rewrites `app/events/refresh.py`. It must keep the
  `async with NominatimGeocoder(...)` scope added here, so that one geocoder and one client cover
  `run_sources` plus `retry_failed_geocodes` in a cycle.
- **#6 `inject-settings-and-clock`**: `app/http.py` takes plain values (a UA string, a timeout) and
  never reads `get_settings()`, which fits that change's direction. ChattZoo's `_now` clock seam
  belongs to #6, and the shared HTTP helper here does not absorb it. ChattZoo tests keep pinning
  `_now` separately.
- **#8 `add-typed-contracts`**: reworks the news registry into dataclasses. This change removes
  `USER_AGENT` from `app/news/registry.py` first. #8 must not add it back.
- **#11 `tighten-python-tooling`**: could add a ruff `flake8-tidy-imports` banned-api rule for
  `httpx.AsyncClient` outside `app/http.py`, enforcing Decision 1 statically. That would be its
  scope, not this change's. Here the rule is pinned by a test (see spec).

## Goals / Non-Goals

**Goals:**
- One place constructs outbound httpx clients. Each call site states its User-Agent, timeout and
  redirect policy explicitly.
- One named browser User-Agent constant.
- One test seam and one test helper. Tests cannot reach the real network by accident.
- Each call site's request settings are pinned by a test, so a refactor that changes them fails
  CI.
- Geocoding reuses one client per refresh cycle.

**Non-Goals:**
- Changing any upstream's User-Agent, timeout or redirect policy, including giving the default-UA
  sources (Meetup, iCal, tribe, CitySpark) an identifying UA. See Open Questions.
- Long-lived clients for collectors or sources across polls. That needs lifespan wiring and buys
  little at 1–5 minute intervals. A client per `fetch()` stays.
- Retries, backoff or rate limiting in the factory. The geocoder's spacing stays where it is.
- Moving feedparser onto httpx.
- Restructuring how settings reach sources (#6) or how refreshes are orchestrated (#4).

## Decisions

### 1. `app/http.py`: a factory with required keyword arguments

```python
BROWSER_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"

def make_client(
    *,
    timeout: float,
    user_agent: str | None,          # None = httpx's default UA, deliberately
    follow_redirects: bool,
    headers: Mapping[str, str] | None = None,
) -> httpx.AsyncClient: ...
```

`timeout`, `user_agent` and `follow_redirects` have **no defaults**. A factory with defaults would
hide the differences that matter here: it would be easy to drop a `follow_redirects=True` or to give
a default-UA source an identifying UA without noticing. With required arguments, a reader sees each
site's settings in the call, and a reviewer sees any change to them in the diff. `None` for
`user_agent` is how a site says "httpx default". Tribe and CitySpark use it on purpose, per their
docstrings. Meetup and iCal use it because they always have.

The User-Agent goes into the client's default headers. Today the geo collectors, the geocoder and
CarCruiseFinder pass it per request. The request carries the same header and value either way.
Header order may differ, and none of these upstreams depends on header order. Other headers stay
where they are: per-request headers (`X-API-Key`, `Authorization`, `Origin`, …) remain per-request,
and Weather's `Accept` goes through `headers=`.

`app/http.py` imports nothing from `app.config`. Callers pass the UA string (`settings.user_agent`,
`settings.events_geocoder_user_agent`, `BROWSER_USER_AGENT`, or `None`).

*Alternatives:* (a) An enum of UA policies (`APP`, `BROWSER`, `DEFAULT`). The geocoder has its own
setting, so the enum would still need a free-string case, and it would hide the actual value from a
reader. (b) Named presets per upstream class ("scraper", "api"). These would recreate implicit
defaults. (c) Naming the module `app/httpclient.py` to avoid any `http` name collision. Not needed:
Python 3 imports are absolute, so `app.http` never shadows the stdlib `http`. Nothing in the repo
puts `app/` itself on `sys.path` (uvicorn, pytest and Alembic all run from the repo root).

### 2. Test seam: module-level transport override, not constructor injection

`app/http.py` holds `_transport: httpx.AsyncBaseTransport | None = None`. `make_client` passes it to
`httpx.AsyncClient(transport=...)`. `None` means real HTTP. Tests set it with `monkeypatch`, which
restores it after each test.

Why not inject a client or transport through each constructor:
- The clients are built deep in code that builders create from `Settings`: `build_collectors()`,
  `build_sources()`, `events.refresh()`, and the module-level `weather_service` singleton that the
  scheduler uses. Injection would mean threading a `transport` parameter through each builder, the
  scheduler and refresh, and that is the code #4 and #6 are already reshaping. A global seam lets
  this change land without touching those signatures.
- One seam covers every path. Tests that drive `refresh()` or a scheduler job end to end (e.g.
  `tests/test_api_events.py`, `tests/test_live_signals.py`) are covered with no extra wiring.
- It makes Decision 3's default-deny guard possible. Constructor injection can't protect code that
  a test forgot to inject into.
- Precedent: `WeatherService._transport` is already this pattern, scoped to one class. This change
  widens it and removes the per-class copy.

Cost: it is global mutable state. That is acceptable here because pytest runs tests sequentially
within a process (pytest-asyncio uses function-scoped loops, and xdist workers would be separate
processes), and `monkeypatch` guarantees the restore. Production code never writes `_transport`.

### 3. One test helper, plus a default-deny guard

`tests/mock_http.py` (not `tests/http.py`, to rule out any stdlib shadowing) provides a small
recorder: it wraps a handler in `httpx.MockTransport` and keeps the list of `httpx.Request`s sent,
so tests can assert on URL, headers and `request.extensions["timeout"]`. A `mock_http` fixture in
`tests/conftest.py` installs it into `app.http._transport` and returns the recorder.

An autouse fixture installs a **deny** transport by default. It records any request a test sends
without installing a mock, and fails the test at teardown with the offending URLs. The guard fails
at teardown instead of only raising inside the request because `run_sources()`, `fetch_all()` and
the scheduler isolate per-source errors on purpose. A raise alone would be swallowed and would show
up as "zero events", which could let a test pass. `tests/test_api_routes.py` builds its own
`httpx.AsyncClient(transport=ASGITransport(...))` against the app. That is a test client, not an
outbound fetch, and it does not go through the factory, so the guard does not affect it.

The five per-file helpers and `WeatherService._transport` are deleted. ChattZoo's `_now` pin stays
as its own one-line `monkeypatch` in that test file.

### 4. A request-settings test pins the Context table

A new parametrized test (`tests/test_http_wire.py`) runs each httpx call site's `fetch` (or
`geocode`, or the weather refresh) once through `mock_http`. For each site it asserts:

- the `User-Agent` header equals the expected string, or starts with `python-httpx/` for
  default-UA sites;
- `request.extensions["timeout"]` matches the table;
- the redirect policy: the handler answers the first request with a 302. A site that follows
  redirects makes a second request. A site that does not makes none.
- the site-specific headers in the table.

This test is what turns "behaviour preserved" from a code-review claim into something CI checks. It
also gives the geo collectors, Meetup, iCal and `_fetch_html` their first fetch coverage. Fuller
behavioural tests for those paths (pagination, 204 handling in TDOT, error status) go in each
source's own test module, using the same fixture. A separate assertion checks that `_parse_feed`
passes `agent=BROWSER_USER_AGENT` to feedparser (patch `feedparser.parse` and inspect the call).

### 5. `NominatimGeocoder` holds one client per lifetime

`NominatimGeocoder` gains `__aenter__`/`__aexit__`. The client is created on enter (with the
geocoder's UA, `timeout`, and redirects not followed) and closed on exit. `geocode()` raises
`RuntimeError` if called outside the context. A second code path that builds a client per call
would keep the bug this decision fixes. `events.refresh()` wraps the cycle in
`async with NominatimGeocoder(...) as geocoder:`, so `run_sources` and `retry_failed_geocodes`
share it, as they already share the rate limiter.

This is the change's **one observable wire difference**: lookups in a cycle reuse keep-alive
connections to `nominatim.openstreetmap.org`. Each request's method, URL, query, headers and timeout
are unchanged. Slot spacing (`min_interval`) is unchanged because it is enforced before each send,
whatever the connection. Nominatim's usage policy limits request rate and asks for an identifying
UA. Connection reuse is within that policy.

The abstract `Geocoder` base and `tests/fakes.py::FakeGeocoder` don't change. Ingest still accepts
any `Geocoder`. `tests/test_live_signals.py` stubs `NominatimGeocoder` with `lambda **kw: object()`
and must switch to a stub that supports `async with`.

*Alternative:* leave the per-query client alone and only route it through the factory. That is
simpler, but it misses the review's finding, and a refresh can issue dozens of lookups.

### 6. Spec placement: a new `outbound-http` capability

The per-feature specs (`news`, `events`, `weather`) already state each upstream's User-Agent
requirement, and those statements stay true. No delta is needed there. What's new is cross-cutting:
the single factory, the shared browser constant, the full request-settings table, the geocoder's
client scope and the test seam. Those go in a new `outbound-http` capability, following the
precedent of `test-isolation` and `code-quality-tooling` for engineering-facing capabilities. The
no-real-network test guard could also sit in `test-isolation`, but that spec's purpose is
database-only. Keeping all HTTP concerns in one spec puts the guard next to the seam it depends on.

## Risks / Trade-offs

- [A call site's settings change by accident during the refactor] → Decision 4's test pins each
  row, and its expected values are copied from the Context table, which records `main` before
  the change. The reviewer checks the test's table against the Context table, not against the
  refactored code.
- [Global seam leaks between tests] → Only `monkeypatch` writes it, and monkeypatch restores it
  after each test. The autouse deny fixture installs a fresh deny transport for each test.
- [Default-deny turns a currently passing test red] → That test is making real network calls
  today, so it is a latent flake that the guard has found. Fix it by mocking, not by weakening the
  guard. In the current tree no test is expected to trip it: `test_api_events` refreshes with
  `build_sources` stubbed to `[]`.
- [Geocoder misuse outside `async with`] → `geocode()` raises immediately with a clear message
  rather than silently opening a client.
- [Code added later bypasses the factory] → A test asserts that no `httpx.AsyncClient(` appears in
  `app/` outside `app/http.py`. A ruff banned-api rule could replace that test later (#11).

## Migration Plan

Code-only refactor with no data, schema or config migration. Rollback is a revert. Deploy is the
usual rebuild. After deploy, check that one news cycle, one events cycle and one weather refresh
succeed. Look at `news_feeds.last_status`, the events refresh log line and the home weather strip.
No Local 3 feed should be at 429 and CarCruiseFinder should not return 403.

## Open Questions

- Meetup and iCal send httpx's default UA, and neither docstring says that is deliberate (tribe's
  and CitySpark's do). Should they move to `settings.user_agent`? That is a wire change, so this
  change leaves it out. It would be a one-argument follow-up after this lands.
- Is default-deny welcome as part of this change, or should it be its own change? It is included
  because it costs one fixture once the seam exists, and the risk of missing a real network call
  in a test is what makes the seam worth having.
