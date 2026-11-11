## 1. Factory and test seam

- [ ] 1.1 Add `app/http.py`: `BROWSER_USER_AGENT` (the current `registry.USER_AGENT` string, with a comment merging the TownNews 429 and CarCruiseFinder 403 reasons), `_transport: httpx.AsyncBaseTransport | None = None` (test-only seam, commented as such), and `make_client(*, timeout, user_agent, follow_redirects, headers=None)` with no defaults on the first three; `user_agent=None` sets no `User-Agent` header so httpx's default goes out. No `app.config` import (superseded by 9.1: `user_agent` defaults to the `user_agent` setting)
- [ ] 1.2 Add `tests/mock_http.py`: a recorder wrapping a handler in `httpx.MockTransport` and keeping the sent `httpx.Request`s
- [ ] 1.3 In `tests/conftest.py` (below the DATABASE_URL override block), add a `mock_http` fixture that installs a recorder into `app.http._transport` via `monkeypatch` and returns it, and an autouse fixture that installs a deny transport, records any unmocked request, and fails the test at teardown listing the URLs
- [ ] 1.4 Add `tests/test_http.py`: factory unit tests (UA set vs `None` → `python-httpx/` default, timeout and `follow_redirects` applied, `headers` merged, override transport used), a test that `httpx.AsyncClient(` appears in `app/` only in `app/http.py`, and a test that the browser UA literal appears only in `app/http.py` (the `None` case is superseded by 9.5)

## 2. Request-settings pin test

- [ ] 2.1 Add `tests/test_http_wire.py`: one parametrized case per httpx call site in design.md's Context table, driving the real `fetch`/`geocode`/weather refresh through `mock_http` and asserting the `User-Agent` (exact, or `python-httpx/` prefix), `request.extensions["timeout"]`, the site-specific headers, and redirect behaviour (handler answers the first request with a 302; a second request happens only for follow-redirect sites). Copy expected values from the design table, not from the refactored code (the `python-httpx/` case is superseded by 9.6)
- [ ] 2.2 In the same module, assert `_parse_feed` calls `feedparser.parse` with `agent=BROWSER_USER_AGENT` and the existing `Accept` request header (patch `feedparser.parse`)

## 3. Move call sites onto the factory

- [ ] 3.1 Geo collectors `app/collectors/{hc911,tdot,epb,tnaw}.py`: `make_client(timeout=30, user_agent=self.settings.user_agent, follow_redirects=False)`; drop `User-Agent` from the per-request header dicts, keep every other header per-request (UA argument dropped by 9.3)
- [ ] 3.2 `app/events/sources/chattzoo.py`: `make_client(timeout=self.timeout, user_agent=self.user_agent, follow_redirects=True)`; make the `user_agent` constructor argument required (remove the `"LocalDash/0.1"` default) (superseded by 9.3: the argument is removed)
- [ ] 3.3 `app/events/sources/{meetup,cityspark}.py`: `user_agent=None, follow_redirects=False`; `{ical,tribe}.py`: `user_agent=None, follow_redirects=True`; timeouts from `self.timeout`; Meetup keeps its `Authorization`/`Content-Type` per-request headers (`user_agent=None` dropped by 9.4)
- [ ] 3.4 `app/events/sources/carcruisefinder.py`: delete `BROWSER_UA`, use `make_client(timeout=self.timeout, user_agent=BROWSER_USER_AGENT, follow_redirects=True)`, and point the module docstring at `app.http.BROWSER_USER_AGENT`
- [ ] 3.5 `app/news/registry.py`: delete `USER_AGENT` and its comment; `app/news/fetcher.py`: import `BROWSER_USER_AGENT` from `app.http` for `_parse_feed` (`agent=`) and use `make_client(timeout=30, user_agent=BROWSER_USER_AGENT, follow_redirects=True)` in `_fetch_html`; update the module docstring's `registry.USER_AGENT` reference
- [ ] 3.6 `app/weather/service.py`: delete the `_transport` class attribute; `_make_client` returns `make_client(timeout=10.0, user_agent=settings.user_agent, follow_redirects=True, headers={"Accept": "application/geo+json"})` (UA argument dropped by 9.3)

## 4. Geocoder client lifetime

- [ ] 4.1 `app/events/geocoding.py`: give `NominatimGeocoder` `__aenter__`/`__aexit__` that open/close one `make_client(timeout=self.timeout, user_agent=self.user_agent, follow_redirects=False)`; `geocode()` uses it and raises `RuntimeError` when not entered; keep the slot spacing, candidate-query fallback and error handling unchanged
- [ ] 4.2 `app/events/refresh.py`: wrap the cycle in `async with NominatimGeocoder(...) as geocoder:` so `run_sources` and `retry_failed_geocodes` share it

## 5. Migrate existing tests

- [ ] 5.1 `tests/test_events_cityspark.py`, `tests/test_events_carcruisefinder.py`, `tests/test_events_tribe.py`: delete `install_transport`, use `mock_http`
- [ ] 5.2 `tests/test_events_chattzoo.py`: delete `_client_transport` and the `AsyncClient` part of `_patch_client`, use `mock_http`; keep the `_now` pin
- [ ] 5.3 `tests/test_events_geocoding.py`: delete both `install_transport` and `install_query_transport`, use `mock_http` (timing recorded in the handler), and run every geocoder under `async with`; add tests that one client serves several lookups and is closed on exit, and that `geocode()` outside the context raises without sending
- [ ] 5.4 `tests/test_weather.py`: replace `svc._transport = httpx.MockTransport(...)` with the shared seam (the per-URL fixture handler class stays)
- [ ] 5.5 `tests/test_live_signals.py`: replace the `lambda **kw: object()` `NominatimGeocoder` stub with one that supports `async with`

## 6. Fill fetch-path coverage

- [ ] 6.1 Add `fetch()` tests for the four geo collectors (in `tests/test_hc911_normalize.py`, `tests/test_tdot.py`, `tests/test_epb.py`, `tests/test_tnaw.py`): success returns the payload shape `normalize()` expects; a non-2xx raises; TDOT skips a 204 endpoint; multi-endpoint/service/layer collectors request each one
- [ ] 6.2 Add `fetch()` tests for Meetup (`tests/test_events_meetup.py`: GraphQL POST body and bearer header, parse of the response) and iCal (`tests/test_events_ical.py`: fetched calendar is parsed, non-2xx raises)
- [ ] 6.3 Add a `_fetch_html` test (`tests/test_news_html_scrape.py`): returns the body on 2xx, raises on non-2xx

## 7. Docs

- [ ] 7.1 `AGENTS.md` news "Feed gotchas": replace "the browser `USER_AGENT` in `registry.py`" with `BROWSER_USER_AGENT` in `app/http.py`
- [ ] 7.2 `AGENTS.md` "HTTP client — httpx" tech-stack paragraph: add that all outbound clients come from `app/http.py`'s `make_client` (explicit timeout/UA/redirects per call), that tests mock upstreams with the `mock_http` fixture, and that unmocked outbound requests fail the test (UA wording revised by 9.10)
- [ ] 7.3 `AGENTS.md` "Adding a data source": note that `fetch()` builds its client with `app.http.make_client`
- [ ] 7.4 Check `CONTRIBUTING.md` and `README.md` for references to `registry.USER_AGENT`, `BROWSER_UA`, or patching `httpx.AsyncClient` in tests, and update any found

## 8. Verify

- [ ] 8.1 `grep -rn "httpx.AsyncClient(" app` matches only `app/http.py`; `grep -rn "Gecko/20100101" app` matches only `app/http.py`
- [ ] 8.2 Run the full test suite and `pre-commit run --all-files`; all pass
- [ ] 8.3 Rebuild and restart (`sg docker -c 'docker compose up --build -d'`), trigger `POST /api/v1/news/refresh`, `POST /api/v1/events/refresh` and load `/api/v1/weather/current`; confirm no news feed's `last_status` is a 429, CarCruiseFinder yields events (no 403), the events refresh log line shows geocoding ran, and weather returns 200

## 9. Default User-Agent (revision in review of #344)

- [ ] 9.1 `app/http.py`: change the signature to `make_client(*, timeout, follow_redirects, user_agent: str | None = None, headers=None)`; omitted or `None` reads `get_settings().user_agent` inside `make_client` at call time (not at import); an explicit blank override (`""` or whitespace) raises `ValueError`; there is no way to send httpx's default UA. Import `get_settings` from `app.config` and confirm there is no import cycle. Update the module docstring and comments
- [ ] 9.2 `app/config.py`: `user_agent` and `events_geocoder_user_agent` reject blank (empty or whitespace) values at load; defaults unchanged
- [ ] 9.3 Stop passing the app's standard UA: hc911, TDOT, EPB, TNAW collectors, `WeatherService._make_client`, and `ChattZooSource`. Remove `ChattZooSource`'s `user_agent` constructor argument and stop passing it in `build_sources()`
- [ ] 9.4 Meetup, iCal, tribe and CitySpark: drop `user_agent=None` so they send the `user_agent` setting. Update the docstrings that describe the UA sent (tribe's "accepts the default User-Agent", CitySpark's, ChattZoo's)
- [ ] 9.5 `tests/test_http.py`: the default UA is the setting; an explicit override is sent; a blank override raises; no client sends `python-httpx/`
- [ ] 9.6 `tests/test_http_wire.py`: update the expected table from the revised spec (the four former httpx-default sources expect the `user_agent` setting); remove the httpx-default path; assert over every pinned site that the UA is non-empty and does not start with `python-httpx/`
- [ ] 9.7 Settings tests: a blank `user_agent` or `events_geocoder_user_agent` fails to load
- [ ] 9.8 Update the ChattZoo tests and any other test passing a removed argument
- [ ] 9.9 Add a test that fails if any `make_client(` call in `app/` passes `user_agent=None`, or passes `user_agent=` at a site other than the three sanctioned overrides (CarCruiseFinder, the news HTML scrape, the Nominatim geocoder)
- [ ] 9.10 `AGENTS.md` "HTTP client — httpx" paragraph: timeout and redirects are explicit per call; the UA defaults to the `user_agent` setting and is passed only to override it; no request sends httpx's default or an empty UA
- [ ] 9.11 Live check (read-only, a handful of requests): for each configured tribe site, each configured iCal feed and the CitySpark endpoint, send the request the source sends once with the app UA and once with `python-httpx/<version>`, and record both statuses in the PR. Meetup needs a token; skip it if none is configured. If an upstream accepts httpx's default but rejects the app UA, stop and ask the owner
- [ ] 9.12 Run the full test suite, `ruff check`, `ruff format --check` and `openspec validate add-shared-http-client --strict`; all pass
