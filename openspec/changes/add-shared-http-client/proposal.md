## Why

The backend builds its outbound HTTP clients in 13 places, each with its own `httpx.AsyncClient(...)`
call, its own timeout (10, 20 or 30 seconds), and its own choice of whether to follow redirects.
The User-Agent is chosen four different ways: `settings.user_agent`, a browser string, the geocoder's
own setting, or httpx's default. The browser string is copied twice (`USER_AGENT` in
`app/news/registry.py` and `BROWSER_UA` in `app/events/sources/carcruisefinder.py`), and
`ChattZooSource` repeats the `"LocalDash/0.1"` default from `config.py`. Only `WeatherService` has a
test seam (`_transport`). Every other fetch test monkeypatches `httpx.AsyncClient` by dotted path,
and five test modules each carry their own copy of that helper. The fetch paths that have no copy
have no tests at all: the four geo collectors, Meetup, iCal, and the news HTML scrape.
`NominatimGeocoder` also opens a new client, with a new connection, for every query.

The User-Agent rules are some of the most fragile behaviour in the app. AGENTS.md lists them under
three "don't regress" sections: TownNews returns 429 to unfamiliar UAs, CarCruiseFinder returns 403
to short UAs, and NWS requires an identifying UA. Today nothing checks them except reading the code.

## What Changes

- New module `app/http.py` with one client factory. Each call site passes its timeout and its
  redirect policy as required keyword arguments, so a site's request settings are visible where it
  makes the request. The User-Agent defaults to the app's `user_agent` setting (read by the factory
  when it builds the client); a call site passes one only to override it. Every client sends a
  non-empty User-Agent: there is no way to request httpx's default, and a blank override raises.
  The module also holds the test seam, a module-level transport override.
- Three User-Agent overrides remain, each required by a main spec: `BROWSER_USER_AGENT` for
  CarCruiseFinder and the news HTML scrape, and `events_geocoder_user_agent` for Nominatim.
- `BROWSER_USER_AGENT` in `app/http.py` replaces `app.news.registry.USER_AGENT` and
  `carcruisefinder.BROWSER_UA`. The news fetcher's feedparser path (`_parse_feed`, which uses
  urllib, not httpx) imports the same constant.
- All 13 `httpx.AsyncClient(...)` constructions under `app/` move to the factory. Every call site
  keeps the timeout, redirect policy and other headers it sends today. Every call site keeps its
  User-Agent except Meetup, iCal, tribe and CitySpark, which move from httpx's default
  (`python-httpx/<version>`) to the `user_agent` setting. Design.md lists them per site.
- `WeatherService._transport` is removed. Its tests use the shared seam.
- `ChattZooSource` loses its `user_agent` constructor argument (and with it the repeated
  `"LocalDash/0.1"` default); `build_sources()` stops passing it. The factory supplies the UA.
- The `user_agent` and `events_geocoder_user_agent` settings reject blank values at load.
- `NominatimGeocoder` becomes an async context manager that holds one client for its lifetime.
  `events.refresh()` opens it with `async with`, so one refresh cycle shares one connection pool
  instead of opening a client per query.
- Tests: one shared mock-transport fixture replaces the five per-file `AsyncClient` monkeypatch
  helpers. An autouse guard fails any test that makes an outbound request without a mock. A new
  test pins each call site's request settings (User-Agent, timeout, redirects, site-specific
  headers). The previously untested fetch paths get coverage.
- AGENTS.md: the news-feed gotcha points at `app.http.BROWSER_USER_AGENT`, and a short note says new
  upstream fetches go through `app/http.py`.

**Observable changes:**
- The geocoder's connection reuse. Nominatim lookups in one refresh cycle now share keep-alive
  connections instead of opening a new TCP/TLS connection per query. The request line, headers,
  timeout and the ≥1 s spacing between requests do not change.
- The User-Agent of the Meetup, iCal, tribe and CitySpark sources, which now send the app's
  `user_agent` setting instead of `python-httpx/<version>`. This was added in review of #344: no
  request should go out with httpx's default or an empty User-Agent. Each configured tribe site,
  iCal feed and the CitySpark endpoint is checked live with both UAs before it ships.

No other request to any upstream changes.

## Capabilities

### New Capabilities
- `outbound-http`: how the backend makes requests to upstream services. All clients come from one
  factory. Each upstream's User-Agent, timeout and redirect policy is pinned. One browser
  User-Agent constant is shared. The geocoder keeps one client per refresh cycle. Tests swap the
  transport and cannot reach the real network.

### Modified Capabilities
None. The User-Agent statements already in `news` ("Scheduled feed fetching with per-feed error
isolation"), `events` (CarCruiseFinder, CitySpark, tribe, zoo, geocoding) and `weather` ("Identifying
User-Agent on upstream requests") stay true as written. CitySpark and tribe "SHALL NOT send a
spoofed browser User-Agent", which the `user_agent` setting is not, and no main spec says any
source sends httpx's default. This change makes them testable and does not change them.

## Impact

- New: `app/http.py` (imports `get_settings` from `app.config` for its default User-Agent; no
  import cycle), a shared mock-HTTP test helper and fixture, and a request-settings test module.
- Edited: `app/collectors/{hc911,tdot,epb,tnaw}.py`, `app/events/geocoding.py`,
  `app/events/refresh.py`, `app/events/sources/{chattzoo,meetup,ical,tribe,cityspark,carcruisefinder}.py`,
  `app/news/fetcher.py`, `app/news/registry.py` (constant removed), `app/weather/service.py`.
- Tests: `tests/conftest.py`, `tests/test_events_{cityspark,chattzoo,carcruisefinder,tribe,geocoding}.py`,
  `tests/test_weather.py`, `tests/test_live_signals.py` (its `NominatimGeocoder` stub must support
  `async with`), plus new fetch tests for the geo collectors, Meetup, iCal and the news HTML scrape.
- `app/config.py`: blank-value validation on `user_agent` and `events_geocoder_user_agent`
  (defaults unchanged).
- Wire: Meetup, iCal, tribe and CitySpark send the `user_agent` setting instead of httpx's default.
- Docs: `AGENTS.md`.
- No new dependencies, no migration, no API or frontend change.
