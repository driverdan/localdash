## Context

The events feature has a pluggable source interface (`app/events/sources/base.py`): a source
subclasses `EventSource`, implements `async fetch() -> list[RawEvent]`, and is registered in
`build_sources()` (`app/events/sources/__init__.py`) gated on config. Ingest
(`app/events/ingest.py`) handles dedup (`canonical_key(title, start_time)`), tagging, geocoding,
and persistence; `run_sources()` already isolates per-source failures (a raising source is
logged and skipped, the cycle continues).

Target site facts (verified live 2026-07; do not re-verify with heavy crawling):

- Listing: `https://carcruisefinder.com/car-shows/tag/chattanooga-tn/` (the old
  `/tag/chattanooga-tn/` URL 301s here). Returns 200 **only** with a real browser User-Agent; a
  generic/short UA gets Cloudflare 403.
- The site runs WordPress "The Events Calendar", but its machine endpoints are WAF-blocked:
  `?ical=1` → 403, `/wp-json/tribe/events/v1/events` → 403, even with a browser UA. HTML
  scraping is the only route.
- Event detail pages from this plugin typically embed schema.org `Event` JSON-LD
  (`<script type="application/ld+json">`), which is far more stable than CSS selectors.

The project uses async `httpx` everywhere (see `app/events/sources/ical.py`, `meetup.py`) and
has no HTML parser in `pyproject.toml`.

## Goals / Non-Goals

**Goals:**

- One new scraper source producing `RawEvent`s from the CarCruiseFinder Chattanooga tag listing.
- Explicitly experimental: `events_carcruisefinder_enabled: bool = False` — off by default.
- Polite scraping: low request rate, small per-run page budget, browser UA (which the site
  demonstrably requires), delays between requests.
- Extraction that degrades gracefully: JSON-LD first, HTML selectors as fallback, per-event
  skip-on-parse-failure.
- Offline-testable parsing: pure functions over saved HTML/JSON-LD fixtures.

**Non-Goals:**

- No WAF circumvention beyond the browser UA the site requires for its human-facing pages (no
  header spoofing arms race, no JS rendering, no proxy rotation). If Cloudflare starts blocking,
  the source fails and logs — we do not escalate.
- No pagination crawl beyond a bounded first page(s) of the listing.
- No dedup improvements: near-duplicates from slightly different titles vs. the
  carsandcoffeeevents.com iCal feed (companion proposal) are accepted.
- No changes to ingest, models, migrations, API, scheduler, or frontend.
- No response caching layer / conditional GETs (nice-to-have; the hourly refresh interval and
  small page budget keep volume low enough without it).

## Decisions

### 1. HTML scraping of listing + detail pages, JSON-LD first

**Decision:** `fetch()` GETs the listing page, extracts event detail URLs, then fetches each
detail page (up to a budget) and extracts one `RawEvent` per page: prefer the schema.org `Event`
JSON-LD block; fall back to The Events Calendar's HTML structure (title from `h1`/entry-title,
`.tribe-events-*` date/venue elements) when JSON-LD is absent or unparseable.

**Why:** the machine endpoints are 403-blocked, so scraping is the only route. JSON-LD carries
structured `startDate`/`endDate`/`location.name`/`location.address` and is a published contract
of the plugin — much less brittle than selectors. Detail pages are needed because the listing
alone lacks reliable full dates/venues.

**Alternative considered:** listing-page-only scraping (one request per run). Rejected: dates on
listing cards are abbreviated/ambiguous and addresses absent, which would poison
`canonical_key` matching and geocoding.

### 2. Parsing dependency: `beautifulsoup4`

**Decision:** add `beautifulsoup4` (with the stdlib `html.parser` backend) to project
dependencies.

**Why over `selectolax`:** BS4 is the most widely known HTML-parsing library (maintenance
familiarity beats raw speed here — we parse a handful of pages per hour, performance is
irrelevant), tolerates malformed markup well, and needs no compiled extension beyond what it
vendors. `selectolax` is faster but that buys nothing at this volume. Using the stdlib parser
backend avoids adding `lxml`.

**JSON-LD note:** JSON-LD extraction is `json.loads` on `<script type="application/ld+json">`
contents found via BS4 — no extra dependency (e.g. `extruct`) is warranted for one schema type.

### 3. Politeness and fragility containment

- **Browser UA:** send a fixed, realistic desktop-browser User-Agent string as a module
  constant. Rationale recorded in the module docstring: the site 403s generic UAs on its
  human-facing pages; this mirrors the hard-won ChattNews/TownNews precedent already in this
  codebase (`app/news/registry.py`).
- **Request budget:** cap detail-page fetches per run (constant, e.g. 25) and sleep a fixed
  delay (~1–2 s) between requests via `asyncio.sleep`. One listing page + ≤ budget detail pages
  per hourly refresh is a trivially polite load.
- **Timeouts:** follow the existing source style (`httpx.AsyncClient(timeout=..., follow_redirects=True)`).
- **Per-event resilience:** a detail page that fails to fetch or parse is logged and skipped;
  the run still returns the events that did parse. A listing-page failure raises, and
  `run_sources()`'s existing isolation confines it to this source.
- **Default off:** `events_carcruisefinder_enabled: bool = False`. This is the honest posture
  for a source that can break at any time (WAF policy change, theme/markup change) and whose
  scraping an operator should consciously opt into.

### 4. Field mapping (JSON-LD path)

| RawEvent field    | JSON-LD `Event`                                             |
|-------------------|-------------------------------------------------------------|
| `title`           | `name` (HTML-entity-decoded)                                 |
| `description`     | `description` (tags stripped, whitespace collapsed)          |
| `start_time`      | `startDate` (ISO 8601; naive values assumed America/New_York, then → UTC) |
| `end_time`        | `endDate`, same handling; `None` if absent                   |
| `venue_name`      | `location.name`                                              |
| `address`         | `location.address` (`PostalAddress` parts joined: street, locality, region, postal) |
| `source_url`      | the detail page URL (canonical `url` if present)             |
| `source_event_id` | the detail page URL slug (stable per event on this site)     |
| `source_name`     | `"CarCruiseFinder"` (constant — one link per event via ingest's `(event, source_name)` uniqueness) |

Events with no parseable start date are skipped (matches the iCal source's rule and the events
spec's "sources supply addresses, not coordinates" — no coordinates are emitted even if JSON-LD
carries `geo`; ingest's geocoder owns coordinates).

**Timezone note:** The Events Calendar usually emits offset-qualified ISO dates; when the offset
is missing, assume the venue-local zone (America/New_York for Chattanooga) rather than UTC,
since these are local car meets and a UTC misread shifts the `canonical_key` hour and breaks
cross-source dedup with the iCal feed.

### 5. Structure for testability

Mirror `ICalSource`: network in `fetch()`, parsing in pure functions —
`parse_listing(html) -> list[str]` (detail URLs) and `parse_detail(html, url) -> RawEvent | None`
(JSON-LD first, selector fallback inside). Tests exercise the pure functions against fixture
files saved under `tests/fixtures/carcruisefinder/` (one listing page snippet, one JSON-LD
detail page, one no-JSON-LD detail page, one undated/broken page); no network in tests.

## Risks / Trade-offs

- **[Cloudflare starts 403-ing scraper traffic]** → Source fails, `run_sources()` logs and
  continues; other sources unaffected. Flag stays available to turn it off permanently. No
  escalation of evasion.
- **[HTML/theme change breaks selectors]** → JSON-LD-first extraction minimizes exposure; the
  selector fallback is best-effort. Breakage manifests as zero events + logs, not corrupt data.
- **[ToS/politeness]** → Default-off, ≤ ~26 requests/hour with delays, no blocked-endpoint
  circumvention. The browser UA is required by the site for pages it serves to humans; we do the
  minimum that works.
- **[Near-duplicate events vs. carsandcoffeeevents.com iCal feed]** → Expected overlap merges
  via `canonical_key(title, start_time)` (one event, one link per source). Slightly different
  titles across sites create near-duplicates — accepted; dedup improvements out of scope.
- **[Naive-datetime timezone guess wrong]** → Worst case is a shifted start hour and a missed
  cross-source merge (two listings instead of one) — annoying, not corrupting. Fixture tests pin
  the chosen behavior.
- **[Listing pagination ignored]** → Far-future events beyond page one may be missed until they
  reach page one; acceptable for an hourly-refresh experimental source.

## Migration Plan

No migrations, no schema, no API changes. Deploy is: install new dependency, ship code; the flag
defaults off so behavior is unchanged. Enable with `EVENTS_CARCRUISEFINDER_ENABLED=true`;
rollback is unsetting the flag (or reverting the code — nothing persists except normally-ingested
events, which are retained by design).

## Open Questions

- Exact detail-page markup fallback selectors must be confirmed against saved fixture HTML at
  implementation time (one or two polite requests to capture fixtures; no heavy crawling).
- Whether the listing paginates for Chattanooga's volume at all — if it's one page, the budget
  constant is moot in practice.
