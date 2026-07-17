# Design: add-chattlibrary-sources

## Context

The news feature adds outlets by editing the code registry (`app/news/registry.py`); the events
feature adds sources by subclassing `EventSource` (`app/events/sources/base.py`) and wiring them
in `build_sources()`. The library's WordPress site was probed 2026-07:

- `https://chattlibrary.org/category/news/feed/` — standard WP RSS, 10 items, identical to the
  site-wide `/feed/` today but scoped to the News category if other post types ever appear.
  (`/news/feed/` is a WP *page* feed and is empty — do not use it.)
- `GET https://chattlibrary.org/wp-json/tribe/events/v1/events` — The Events Calendar (tribe)
  REST API. Supports `start_date`, `end_date`, `per_page` (max 50), `page`; responds with
  `events[]`, `total`, `total_pages`. A 14-day window is ~104 events (3 pages). Accepts the
  default httpx User-Agent (verified — no spoofing needed). Each recurring-series occurrence is
  its own post with a distinct `id` (verified), so occurrence IDs are safe as
  `source_event_id`.
- The iCal export (`/events/?ical=1`) returns only 30 events (~6 days of this calendar) and
  omits images/categories — rejected in the proposal.

## Goals / Non-Goals

**Goals:**

- Library announcements appear in the news feature with fallback category `life`.
- Library events flow through the existing ingest pipeline (dedup, tagging, geocoding) with a
  14-day lookahead, proper source name, images, supplied tags, and supplied coordinates.
- The tribe source is generic: any WordPress + The Events Calendar site can be added by
  configuration alone.
- Parsing is a pure function of the API payload, testable offline (CitySpark precedent).

**Non-Goals:**

- Migrating the Cars and Coffee iCal feed to the tribe source (same plugin; separate change).
- Tribe REST `tags` field ingestion — the library organizes by `categories`; tags can be added
  later if a configured calendar needs them.
- Any frontend change — both features render new sources with existing UI.

## Decisions

### D1: News is a registry-only change

Add a seventh `SOURCES` entry: slug `chattlibrary`, name "Chattanooga Public Library", homepage
`https://chattlibrary.org`, one feed `https://chattlibrary.org/category/news/feed/` with
category `life`. Rationale for `life` (user decision): content is announcement/press-release
flavored, closest to The Pulse's registration. WordPress emits per-item `<category>` tags, so
classify.py's tag mapping still overrides per article when applicable. No fetcher, clustering,
or categorization changes.

### D2: Generic `TribeEventsSource`, not a library-specific scraper

New `app/events/sources/tribe.py` with `TribeEventsSource(base_url, name, lookahead_days,
timeout)`. `fetch()` requests `{base_url}/wp-json/tribe/events/v1/events` with
`start_date=today`, `end_date=today+lookahead`, `per_page=50`, iterating `page` until
`total_pages` is exhausted, with a defensive page cap (10) against pathological calendars.
Dates are venue-local calendar dates (the API interprets them in site-local time; day-boundary
slop is harmless — the window is a fetch horizon, not a display filter). Parsing lives in a
pure `parse(payload) -> list[RawEvent]` function fed one page's JSON, so tests run offline on a
captured fixture. Alternative considered: library-specific source — rejected; nothing in the
mapping is library-specific and the plugin is ubiquitous among local venues.

### D3: Configuration mirrors `events_ical_feeds`

New setting `events_tribe_calendars: str`, comma-separated `Name=BaseURL` entries, default
`Chattanooga Public Library=https://chattlibrary.org`. Empty string disables tribe ingestion;
overriding replaces the default (same contract as `events_ical_feeds`). Entries split on the
first `=`; malformed entries (no `=`) are logged and skipped. A shared
`events_tribe_lookahead_days: int = 14` aligns with the CitySpark lookahead norm. Alternatives:
per-calendar enable flags like CitySpark (doesn't scale past one calendar); reusing
`events_ical_feeds` naming style URL-only (loses the human source name, the existing `iCal:
<url>` display wart this design avoids).

### D4: Field mapping

| RawEvent field | Tribe REST source | Notes |
|---|---|---|
| `title` | `title` | `html.unescape` (WP encodes entities) |
| `description` | `description` | HTML → text via BeautifulSoup `get_text` (bs4 is already an events dependency via carcruisefinder; the frontend renders descriptions as plain text, and reusing `app.news.textutil.strip_html` would couple sibling features) |
| `start_time` | `utc_start_date` | `YYYY-MM-DD HH:MM:SS`, parse as aware UTC; **skip with warning if absent** |
| `end_time` | `utc_end_date` | same parse, optional |
| `venue_name` | `venue.venue` | absent/virtual venue → None |
| `address` | `venue.address, city, stateprovince, zip` joined | only non-empty parts |
| `latitude`/`longitude` | `venue.geo_lat`/`geo_lng` | supplied when present → ingest skips geocoding; missing geo falls back to address geocoding automatically |
| `image_url` | `image.url` | through shared `clean_image_url` |
| `tags` | `categories[].name`, lowercased | supplied tags skip keyword tagging and merge with the topic vocabulary (base.py contract) |
| `source_event_id` | `str(id)` | per-occurrence unique (verified) |
| `source_url` | `url` | the event page (occurrence-dated for recurring events) |
| `source_name` | configured calendar name | e.g. "Chattanooga Public Library" |

### D5: Plain User-Agent, no auth

The endpoint accepts httpx's default UA (verified), matching the CitySpark requirement's
"no spoofed browser User-Agent" stance. The browser-UA precedent (news registry,
carcruisefinder) exists only for WAF'd upstreams and is not imported here.

## Risks / Trade-offs

- [Tribe plugin update changes REST payload shape] → parse defensively (`.get` with fallbacks,
  skip-and-warn per event); breakage manifests as zero events plus logs, contained by
  `run_sources()` per-source failure isolation.
- [3+ requests per calendar per hourly refresh] → trivial load; page cap bounds the worst case.
- [`Name=BaseURL` mini-format in config] → documented next to the setting; malformed entries
  are skipped loudly rather than crashing startup.
- [Recurring storytimes at 5 branches make the events list library-heavy] → accepted; the UI's
  existing tag/source filtering handles it. If it overwhelms, lookahead or calendar list are
  env-tunable without code.
- [Library posts rarely cluster with outlet coverage] → expected; clustering is cross-outlet
  bonus, not a requirement for a source.

## Migration Plan

No migrations. News registry syncs on startup (new source/feed upserted). Events appear on the
next scheduled refresh. Rollback: remove the registry entry (startup sync deletes the feed) and
set `EVENTS_TRIBE_CALENDARS=""` or revert. Per the project convention, rebuild with
`docker compose up --build` after the change.

## Open Questions

None blocking. Follow-up candidates recorded in the proposal (Cars and Coffee migration).
