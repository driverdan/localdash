## 1. Dependency

- [x] 1.1 Add `beautifulsoup4` to `pyproject.toml` dependencies (stdlib `html.parser` backend —
  no `lxml`)
- [x] 1.2 No `app/config.py` change — CarCruiseFinder is a normal source with no per-source
  config flag (registered unconditionally in `build_sources()`, matching iCal/Meetup)

## 2. Fixtures (before parser code — parsers are written against these)

- [x] 2.1 Capture fixture HTML with one or two polite browser-UA requests (no heavy crawling):
  the Chattanooga tag listing page (trimmed to a representative snippet that keeps its JSON-LD
  blocks intact) saved under `tests/fixtures/carcruisefinder/`. (Discovery recorded in
  design.md: the listing embeds complete `Event` JSON-LD for every event, so no detail-page
  fixtures are needed.)
- [x] 2.2 Derive two synthetic fixture variants: one with all JSON-LD blocks removed
  (zero-events case) and one whose event nodes include an undated node (skip case)

## 3. Scraper source

- [x] 3.1 Create `app/events/sources/carcruisefinder.py`: module docstring recording the
  fragility posture, why a browser User-Agent is required (site 403s generic UAs), and why the
  listing page's JSON-LD is used instead of detail pages (detail-page JSON-LD observed with
  wrong UTC offsets); constants for the listing URL and browser UA
- [x] 3.2 Implement pure `parse_listing(html: str, listing_url: str) -> list[RawEvent]`:
  discover `application/ld+json` scripts via BS4, collect `Event` nodes from top-level
  object/array/`@graph` shapes, map fields per design (naive datetimes as America/New_York →
  UTC, joined PostalAddress, entity-decoded title, tag-stripped description, URL-slug source
  event id); skip nodes without a parseable start date; never emit coordinates
- [x] 3.3 Implement `CarCruiseFinderSource(EventSource).fetch()`: single GET of the listing with
  browser UA (httpx, follow_redirects, timeout per existing source style), `raise_for_status`,
  return `parse_listing(...)`
- [x] 3.4 Register in `build_sources()` (`app/events/sources/__init__.py`) unconditionally as a
  normal event source alongside the iCal and Meetup sources (no config flag); verify no
  `pyproject.toml` packages change is needed
- [x] 3.5 (Removed — no detail-page budget/delay machinery exists in the listing-only design)

## 4. Tests (offline — no network)

- [x] 4.1 `tests/test_events_carcruisefinder.py`: `parse_listing` on the real listing fixture
  yields the expected events (count, a spot-checked title, tz-aware UTC start converted from
  the `-04:00` offset, venue name, joined address, source link/id) and no coordinates anywhere
- [x] 4.2 `parse_listing` on the no-JSON-LD fixture returns `[]`; on the undated-node fixture
  skips that node while returning the rest; naive `startDate` values are interpreted as
  America/New_York and converted to UTC
- [x] 4.3 `fetch()` with mocked transport (httpx MockTransport): exactly one request is made, to
  the listing URL, with the browser UA header; an HTTP error raises (contained by
  `run_sources()`)
- [x] 4.4 Registration test: `build_sources()` with default settings registers exactly one
  CarCruiseFinder source alongside the other configured sources

## 5. Verify

- [x] 5.1 Run `pytest` — full suite green, new tests pass offline
- [x] 5.2 Confirm app startup registers the CarCruiseFinder source (no flag required);
  requests to carcruisefinder.com occur only during refresh cycles — run a single manual
  refresh to sanity-check live parsing
- [x] 5.3 `openspec validate add-carcruisefinder-scraper` passes
