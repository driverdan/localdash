## Why

The Chattanooga Zoo runs a steady stream of public family events (Adventure Days, Homeschool
Days, seasonal dress-up days, members-only nights) that none of the existing event sources
carry: the zoo does not syndicate to The Pulse's CitySpark calendar, is not a Meetup group,
publishes no iCal feed, and does not run The Events Calendar. It is a well-known local venue
inside the ingest radius whose events are currently invisible on `/events`.

The zoo's site is a hand-rolled Craft CMS build with no machine endpoint of any kind
(`.ics`, `/feed`, Element API, and `sitemap.xml` all 404; no JSON-LD, microdata, or Open Graph
tags anywhere in the markup), so scraping its human-facing pages is the only route — the same
situation that produced `CarCruiseFinderSource`.

## What Changes

- Add a `ChattZooSource` event source that scrapes the zoo's events listing
  (`https://chattzoo.org/events/zooevents`) and each linked event detail page, registered
  unconditionally in `build_sources()` with no per-source config flag (CarCruiseFinder
  precedent — fragility is contained by `run_sources()`'s per-source failure isolation).
- The source is **two-hop**: the listing page carries only title, image, and detail URL, and
  dates exist **only** on the detail pages. This is the first source that fetches detail pages,
  a deliberate departure from CarCruiseFinder's listing-only rule (which exists there because
  that site's detail pages carry corrupt UTC offsets — a hazard the zoo's pages do not have,
  since they carry no offsets at all).
- Resolve the zoo's **year-less date strings** (`March 22 | 9:00 AM - 5:00 PM`) with a
  nearest-year rule, then drop occurrences already past. The pages retain stale occurrences
  from earlier in the year, so a naive "next occurrence" reading would invent events that do
  not exist.
- **Fan out** each detail page into one raw event per listed occurrence (Adventure Days lists
  four dates on one page), with per-occurrence source event ids so the occurrences do not
  collapse into each other during de-duplication.
- Supply the zoo's fixed venue coordinates directly, so the source adds zero Nominatim traffic.

## Capabilities

### New Capabilities
<!-- None: this adds a source to the existing events capability. -->

### Modified Capabilities
- `events`: adds a new requirement for the Chattanooga Zoo scraper source — its two-hop fetch
  shape, year-less date resolution, per-occurrence fan-out, supplied venue coordinates, and
  failure isolation.

## Impact

- **New code**: `app/events/sources/chattzoo.py` (pure `parse_listing` / `parse_detail`
  functions plus the `EventSource` subclass, matching the CarCruiseFinder layout).
- **Modified code**: `app/events/sources/__init__.py` (register the source in
  `build_sources()`).
- **Tests**: new offline fixtures under `tests/fixtures/` for the listing page and
  representative detail pages (single-date, multi-date, and stale-past-date), exercising the
  pure parse functions with no network access.
- **Docs**: `AGENTS.md` events-source inventory and the "Events source gotchas" list.
- **Dependencies**: none new — `httpx` and `BeautifulSoup` are already used by
  `CarCruiseFinderSource`.
- **Runtime cost**: five HTTP requests per refresh cycle (one listing + four detail pages at
  current volume); no new database tables, migrations, or scheduler jobs; no added geocoder
  load.
- **Risk**: selector-based scraping of a template-driven site with no structured data is
  inherently fragile; breakage manifests as zero zoo events plus logs, never as a failed
  refresh cycle.
