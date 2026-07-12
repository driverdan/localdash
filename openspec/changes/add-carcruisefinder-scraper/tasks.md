## 1. Dependency & config

- [ ] 1.1 Add `beautifulsoup4` to `pyproject.toml` dependencies (stdlib `html.parser` backend —
  no `lxml`)
- [ ] 1.2 Add `events_carcruisefinder_enabled: bool = False` to `app/config.py` with a comment
  marking the source experimental/fragile (WAF-blocked machine endpoints, scraping only)

## 2. Fixtures (before parser code — parsers are written against these)

- [ ] 2.1 Capture fixture HTML with one or two polite browser-UA requests (no heavy crawling):
  the Chattanooga tag listing page and one event detail page; save under
  `tests/fixtures/carcruisefinder/` (trim to representative snippets if pages are huge)
- [ ] 2.2 Derive two synthetic fixture variants from the detail page: one with its JSON-LD block
  removed (HTML-fallback case) and one with no parseable date (skip case)

## 3. Scraper source

- [ ] 3.1 Create `app/events/sources/carcruisefinder.py`: module docstring recording the
  fragility posture and why a browser User-Agent is required (site 403s generic UAs); constants
  for the listing URL, browser UA, per-run detail-page budget, and inter-request delay
- [ ] 3.2 Implement pure `parse_listing(html: str) -> list[str]` returning absolute event
  detail URLs from the listing page (deduplicated, order preserved)
- [ ] 3.3 Implement pure `parse_detail(html: str, url: str) -> RawEvent | None`: JSON-LD
  `Event` first (name, startDate/endDate with naive values interpreted as America/New_York then
  coerced to UTC, location name + joined PostalAddress parts, description with tags stripped);
  HTML selector fallback when JSON-LD is absent/unparseable; return `None` when no start date;
  `source_name="CarCruiseFinder"`, `source_url` = detail URL, `source_event_id` = URL slug;
  never emit coordinates
- [ ] 3.4 Implement `CarCruiseFinderSource(EventSource).fetch()`: GET listing with browser UA
  (httpx, follow_redirects, timeout per existing source style), parse links, fetch up to the
  budget of detail pages with `asyncio.sleep` delay between requests; log and skip a detail
  page that fails to fetch or parse; let a listing-page failure raise (contained by
  `run_sources()`)
- [ ] 3.5 Register in `build_sources()` (`app/events/sources/__init__.py`) gated on
  `settings.events_carcruisefinder_enabled`; add `app.events.sources` packaging is already
  covered — verify no `pyproject.toml` packages change is needed

## 4. Tests (offline — no network)

- [ ] 4.1 `tests/test_events_carcruisefinder.py`: `parse_listing` yields the expected detail
  URLs from the listing fixture
- [ ] 4.2 `parse_detail` on the JSON-LD fixture: correct title, tz-aware UTC start/end, venue
  name, joined address string, source link/id, and no coordinates anywhere on the RawEvent
- [ ] 4.3 `parse_detail` on the JSON-LD-stripped fixture uses the HTML fallback; on the undated
  fixture returns `None`
- [ ] 4.4 `fetch()` with mocked transport (httpx MockTransport): one failing detail page is
  skipped while others still yield events; assert the browser UA header is sent
- [ ] 4.5 Registration test: default settings register no CarCruiseFinder source;
  `events_carcruisefinder_enabled=True` registers exactly one

## 5. Verify

- [ ] 5.1 Run `pytest` — full suite green, new tests pass offline
- [ ] 5.2 With the flag off (default), confirm app startup makes no carcruisefinder.com
  requests (source list unchanged); optionally enable the flag locally for a single manual
  refresh to sanity-check live parsing, then disable
- [ ] 5.3 `openspec validate add-carcruisefinder-scraper` passes
