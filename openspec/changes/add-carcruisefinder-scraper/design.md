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
- Treated as a normal source: registered unconditionally in `build_sources()` alongside the
  iCal and Meetup sources — no per-source config flag. Fragility is contained by
  `run_sources()`'s existing per-source failure isolation (a raising source is logged and
  skipped, the cycle continues), which is how iCal and Meetup already behave.
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

### 1. Listing-page-only scraping, driven by the listing's own `Event` JSON-LD

**Decision:** `fetch()` GETs only the listing page and extracts one `RawEvent` per schema.org
`Event` node found in the page's `<script type="application/ld+json">` blocks (nodes may appear
as a top-level object, a top-level array, or inside a Yoast `@graph`). No detail pages are
fetched and there is no HTML-selector fallback — if the JSON-LD disappears, the source yields
zero events and logs, the accepted failure mode for this fragile source.

**Why (revised at implementation time — the original plan was listing + detail pages):**
fixture capture showed the listing page embeds a complete `Event` JSON-LD array for every
listed event — names, venue names, full `PostalAddress` blocks, and *DST-correct* offsets
(`-04:00` summer, `-05:00` November). The detail pages' own JSON-LD, by contrast, was observed
carrying a wrong offset (`-05:00` on an August event, i.e. EST during EDT), which would shift
the UTC hour in `canonical_key` and break cross-source dedup with the iCal feed. Listing-only is
therefore simultaneously: more correct (right offsets), 26× politer (1 request/run instead of up
to ~26), and less fragile (one page's markup to depend on, and JSON-LD rather than selectors).

**Alternative considered:** the originally-designed listing → detail-page crawl with HTML
fallback. Rejected once the facts were in: strictly more requests, more code, and demonstrably
worse timestamps.

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
- **Request budget:** exactly one listing-page GET per refresh cycle — no delays or budget
  constants needed.
- **Timeouts:** follow the existing source style (`httpx.AsyncClient(timeout=..., follow_redirects=True)`).
- **Per-event resilience:** an `Event` node that fails to parse (no usable start date, malformed
  fields) is logged and skipped; the run still returns the events that did parse. A
  listing-page fetch failure raises, and `run_sources()`'s existing isolation confines it to
  this source.
- **Normal source (no flag):** CarCruiseFinder is registered unconditionally in `build_sources()`,
  matching the iCal and Meetup sources (neither of which has a per-source `*_enabled` flag
  either — iCal is gated by its feed list, Meetup by its token, CarCruiseFinder by neither).
  The source's fragility (WAF policy change, theme/markup change) is contained by
  `run_sources()`'s per-source failure isolation rather than a default-off switch. If the
  source breaks, it contributes zero events and logs; the code can be reverted to remove it.

### 4. Field mapping (listing-page `Event` JSON-LD)

| RawEvent field    | JSON-LD `Event`                                             |
|-------------------|-------------------------------------------------------------|
| `title`           | `name` (HTML-entity-decoded)                                 |
| `description`     | `description` (tags stripped, entities decoded, whitespace collapsed) |
| `start_time`      | `startDate` (ISO 8601; naive values assumed America/New_York, then → UTC) |
| `end_time`        | `endDate`, same handling; `None` if absent                   |
| `venue_name`      | `location.name`                                              |
| `address`         | `location.address` (`PostalAddress` parts joined: street, locality, region, postal, country) |
| `source_url`      | the node's `url` (the event detail page; falls back to the listing URL) |
| `source_event_id` | the detail-URL path slug (stable per event on this site)     |
| `source_name`     | `"CarCruiseFinder"` (constant — one link per event via ingest's `(event, source_name)` uniqueness) |

Events with no parseable start date are skipped (matches the iCal source's rule and the events
spec's "sources supply addresses, not coordinates" — no coordinates are emitted even though this
JSON-LD carries `location.geo`; ingest's geocoder owns coordinates).

**Timezone note:** The Events Calendar usually emits offset-qualified ISO dates; when the offset
is missing, assume the venue-local zone (America/New_York for Chattanooga) rather than UTC,
since these are local car meets and a UTC misread shifts the `canonical_key` hour and breaks
cross-source dedup with the iCal feed.

### 5. Structure for testability

Mirror `ICalSource`: network in `fetch()`, parsing in a pure function —
`parse_listing(html, listing_url) -> list[RawEvent]` (JSON-LD block discovery via BS4, node
extraction, per-node mapping with skip-on-failure). Tests exercise the pure function against
fixture files saved under `tests/fixtures/carcruisefinder/` (a trimmed real listing snippet
with its three JSON-LD blocks, a no-JSON-LD variant, and an undated-event variant); no network
in tests.

## Risks / Trade-offs

- **[Cloudflare starts 403-ing scraper traffic]** → Source fails, `run_sources()` logs and
  continues; other sources unaffected. The source contributes zero events until the block
  lifts or the code is reverted; no escalation of evasion.
- **[Theme/SEO-plugin change removes the listing JSON-LD]** → Source yields zero events + logs;
  no corrupt data. There is deliberately no selector fallback to maintain against a moving
  target.
- **[ToS/politeness]** → One request per hourly refresh, no blocked-endpoint circumvention. The
  browser UA is required by the site for pages it serves to humans; we do the minimum that
  works.
- **[Near-duplicate events vs. carsandcoffeeevents.com iCal feed]** → Expected overlap merges
  via `canonical_key(title, start_time)` (one event, one link per source). Slightly different
  titles across sites create near-duplicates — accepted; dedup improvements out of scope.
- **[Naive-datetime timezone guess wrong]** → Worst case is a shifted start hour and a missed
  cross-source merge (two listings instead of one) — annoying, not corrupting. Fixture tests pin
  the chosen behavior. (Observed listing JSON-LD is offset-qualified and DST-correct, so this
  path is a safety net.)
- **[Listing pagination ignored]** → Far-future events beyond page one may be missed until they
  reach page one; acceptable for an hourly-refresh experimental source (observed volume: 19
  events on one page).

## Migration Plan

No migrations, no schema, no API changes, no config changes. Deploy is: install new
dependency, ship code; the source is registered immediately and runs on the existing
`events_refresh_minutes` schedule. Rollback is reverting the code (nothing persists except
normally-ingested events, which are retained by design).

## Open Questions

None remaining — both original questions were resolved during fixture capture: the listing's
own JSON-LD made detail pages (and their fallback selectors) unnecessary, and Chattanooga's
volume fits on one listing page (19 events).
