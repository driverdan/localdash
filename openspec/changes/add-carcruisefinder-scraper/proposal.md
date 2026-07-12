## Why

Chattanooga-area car events (cruise-ins, car shows, cars & coffee) are poorly covered by the
sources the events feature can consume today: none of the existing iCal/Meetup options carry a
precisely Chattanooga-targeted car-event listing. CarCruiseFinder's Chattanooga tag page
(`https://carcruisefinder.com/car-shows/tag/chattanooga-tn/`) is the most precisely-targeted
listing found — but its machine-readable endpoints (The Events Calendar iCal export and
`/wp-json/tribe/events/v1/events` REST API) are blocked by a Cloudflare WAF (403), so HTML
scraping is the only viable route. The source is inherently fragile (the WAF may start
blocking at any time and HTML structure changes break selectors), but that is contained by
`run_sources()`'s existing per-source failure isolation — it is registered as a normal source
alongside iCal and Meetup, with no per-source config flag.

## What Changes

- Add a new `EventSource` subclass, `CarCruiseFinderSource`
  (`app/events/sources/carcruisefinder.py`), that scrapes the CarCruiseFinder Chattanooga tag
  listing page: parse the listing HTML for event detail links, fetch each detail page, prefer
  schema.org JSON-LD (typical for The Events Calendar plugin), and fall back to HTML selectors.
- Requests use a real browser-like User-Agent (the site returns Cloudflare 403 to generic/short
  UAs — demonstrably required, not evasion for its own sake), a low request rate with polite
  inter-request delays, and a bounded number of detail-page fetches per run.
- Register the source unconditionally in `build_sources()` (`app/events/sources/__init__.py`)
  alongside the iCal and Meetup sources — a normal source with no per-source config flag
  (fragility is contained by `run_sources()`'s existing per-source failure isolation).
- Add an HTML-parsing dependency (`beautifulsoup4`) to `pyproject.toml` — the project currently
  has no HTML parser (only `feedparser` and `icalendar`).
- Offline test coverage: parsing is a pure function of saved HTML/JSON-LD fixture samples; no
  network in tests.
- Expected behavior, documented not changed: many of this site's events will overlap with the
  carsandcoffeeevents.com statewide iCal feed (separate companion proposal); ingest's
  `canonical_key(title, start_time)` merge collapses cross-source duplicates and attaches one
  link per source. Slightly different titles across sites may create near-duplicates — accepted;
  dedup improvements are out of scope.

## Capabilities

### New Capabilities

_None — this extends the existing `events` capability with a new source; the pluggable source
interface, ingest, storage, API, and frontend are unchanged._

### Modified Capabilities

- `events`: add a requirement for the CarCruiseFinder scraper source — registered
  unconditionally as a normal event source (no per-source config flag, matching the iCal and
  Meetup sources' treatment), browser-UA + polite scraping behavior, JSON-LD-first/HTML-fallback
  extraction, and failure isolation (a broken scrape must not affect other sources — already
  guaranteed by `run_sources()`, restated as a requirement for this fragile source).

## Impact

- **Code**: new `app/events/sources/carcruisefinder.py`; one registration block in
  `app/events/sources/__init__.py`; new tests + fixtures under `tests/`.
  No changes to `app/config.py`, `app/events/ingest.py`, models, migrations, API, scheduler, or
  frontend — the source interface guarantees that.
- **Dependencies**: adds `beautifulsoup4` (HTML parsing).
- **Systems / external**: low-rate scraping of carcruisefinder.com (a third-party WordPress
  site behind Cloudflare). Politeness/ToS considerations are acknowledged: minimal request
  volume and no machine-endpoint circumvention (they are simply blocked). The source can break
  silently at any time; per-source failure isolation and logging in `run_sources()` contain the
  blast radius.
- **Default behavior**: the source is registered and runs on the existing
  `events_refresh_minutes` schedule; no new setting is introduced, so enabling the events
  feature (already the default) is sufficient to activate it.
