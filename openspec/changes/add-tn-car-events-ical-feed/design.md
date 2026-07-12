# Design: add-tn-car-events-ical-feed

## Context

The Events feature's source registry (`app/events/sources/__init__.py::build_sources()`) is pure
config: it creates one `ICalSource` per URL in `settings.events_ical_feeds` (comma-separated,
currently defaulting to `""` in `app/config.py`) plus an optional Meetup source. Topic tagging
(`app/events/tagging.py::TOPIC_KEYWORDS`) is a code-defined dict of case-insensitive substring
keywords matched against title + description; there is no "cars" topic today.

A verified live feed exists: `https://carsandcoffeeevents.com/events/category/tennessee/?ical=1`
(WordPress "The Events Calendar" on carsandcoffeeevents.com, a national aggregator). It returns
HTTP 200 with `text/calendar` and 30 upcoming `VEVENT`s carrying real street addresses in
`LOCATION` lines — e.g. the weekly "Ooltewah Cruise In @ Cambridge Square", 9452 Bradmore Ln,
Ooltewah TN (Chattanooga metro). These addresses are exactly what the existing Nominatim geocoder
consumes. (Findings already verified live; do not re-verify during implementation.)

## Goals / Non-Goals

**Goals:**
- A fresh install ingests real car events with zero configuration: ship the Tennessee feed as the
  `events_ical_feeds` config default, overridable (or clearable) via `EVENTS_ICAL_FEEDS`.
- Car events are filterable in the UI via a new `cars` topic in the keyword tagger.
- Update `.env.example` so the documented default matches the code default.

**Non-Goals:**
- **Ingest-side radius filtering.** The feed is statewide Tennessee (Clarksville, White House,
  etc.); distant events are stored but hidden at read time by the existing `max_miles` filter
  from `CHATTANOOGA_CENTER`. Dropping far events at ingest is a separate companion proposal.
- No new source class, API change, migration, scheduler change, or frontend change (topic chips
  come from `GET /api/v1/events/tags` dynamically).
- No retro-tagging of previously ingested events (tagging runs at event creation; moot on a
  fresh install, and this is the first configured source).

## Decisions

1. **iCal over the site's JSON REST API.** The site also exposes
   `/wp-json/tribe/events/v1/events`, but LocalDash already supports iCal via config — the JSON
   route would require a new source class for zero functional gain. Chosen: iCal URL in config.
2. **Ship the feed as the config default, not just documentation.** Alternative: leave the
   default empty and only document the URL in `.env.example`. Rejected because the whole point is
   working-out-of-the-box; env override preserves operator control (set `EVENTS_ICAL_FEEDS=` to
   disable, or replace/extend the list). This relaxes the spec's "no sources are active by
   default" wording: registration stays entirely config-driven, but the shipped configuration now
   includes one feed. The "no importable sample/fixture source" rule is untouched — this is a
   real feed, not fixture data.
3. **Statewide feed accepted; filter at read time.** There is no city-level tag feed on the site
   (verified 404), so Tennessee-wide is the narrowest available. The read API's `max_miles`
   filter already hides distant events; storage of far events is harmless (events are retained
   indefinitely anyway).
4. **`cars` keyword list.** Add to `TOPIC_KEYWORDS`:
   `"car show", "cruise-in", "cruise in", "cars and coffee", "car meet", "hot rod",
   "classic car", "corvette", "mustang", "camaro", "auto show"`.
   Multi-word phrases ("car show", "car meet") rather than a bare "car" keyword avoid false
   positives ("carnival", "daycare"); marque names (corvette/mustang/camaro) catch
   model-specific meets. Both "cruise-in" and "cruise in" are listed because matching is plain
   substring, not tokenized.

## Risks / Trade-offs

- [Third-party feed changes URL/format or goes away] → Feed errors already don't abort an ingest
  cycle (per-source isolation in ingest); operators can override `EVENTS_ICAL_FEEDS`. No new
  handling needed.
- [Statewide events look like noise when browsing without a distance filter] → Documented caveat;
  the UI's distance filter handles it, and the companion ingest-radius proposal can eliminate it
  later.
- [Keyword false positives (e.g. "mustang" in a school-team event name)] → Acceptable for a
  keyword tagger; the same trade-off exists for every current topic. Keywords chosen to be
  specific multi-word phrases where feasible.
- [Nominatim load from ~30 new addresses on first run] → The permanent geocode cache means each
  address is looked up once, ever; volume is trivial.

## Migration Plan

Config-default change only. Deploy normally; the next scheduled refresh (or startup refresh)
ingests the feed. Rollback = revert the default or set `EVENTS_ICAL_FEEDS=` in the environment.
Operators who already set `EVENTS_ICAL_FEEDS` see no behavior change.

## Open Questions

None.
