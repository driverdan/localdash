# Proposal: add-tn-car-events-ical-feed

## Why

The Events feature ships with an empty source registry — a fresh LocalDash install shows zero
events until someone hunts down feed URLs. A live, verified iCal feed of Tennessee car events
(carsandcoffeeevents.com) exists with real street addresses in its `LOCATION` lines, including
recurring Chattanooga-metro events (e.g. the weekly "Ooltewah Cruise In" at Cambridge Square).
Registering it as the default first source makes the feature useful out of the box, and adding a
"cars" topic makes those events filterable in the UI.

## What Changes

- **Default iCal feed**: change the `events_ical_feeds` config default from empty to
  `https://carsandcoffeeevents.com/events/category/tennessee/?ical=1` (verified live: HTTP 200,
  `text/calendar`, 30 upcoming `VEVENT`s with geocodable street addresses). Still a plain
  comma-separated env-overridable setting — operators can replace or clear it via
  `EVENTS_ICAL_FEEDS`. Document the default in `.env.example`.
- **New "cars" topic**: add a `cars` entry to the keyword tagger's `TOPIC_KEYWORDS` map
  (keywords like "car show", "cruise-in", "cruise in", "cars and coffee", "car meet", "hot rod",
  "classic car", "corvette", "mustang", "camaro", "auto show") so ingested car events get a
  filterable topic chip. No frontend change needed — the UI builds chips dynamically from
  `GET /api/v1/events/tags`.
- No new code paths: iCal sources are pure config (`build_sources()` already creates an
  `ICalSource` per URL), and the tagger is a code-defined dict.

**Known caveat (accepted):** the feed is statewide Tennessee (Clarksville, White House, etc.).
Distant events are hidden at read time by the existing `max_miles` filter from the Chattanooga
center; they are still stored. An ingest-side radius filter is a deliberate non-goal here and
belongs in a separate companion proposal. (No city-level tag feed exists on the site — verified
404.)

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `events`: two requirement-level changes:
  1. *iCal feed sources* — the `events_ical_feeds` default changes from empty to the Tennessee
     car-events feed URL (and the "no sources are active by default" wording in the pluggable
     source interface requirement is relaxed accordingly: registration remains entirely
     config-driven, but the config ships with one default feed).
  2. *Keyword topic tagging* — the code-defined topic list gains `cars`.

## Impact

- `app/config.py` — `events_ical_feeds` default value only.
- `app/events/tagging.py` — one new `TOPIC_KEYWORDS` entry.
- `.env.example` — show the new default for `EVENTS_ICAL_FEEDS`.
- `openspec/specs/events/spec.md` — delta for the two requirements above.
- Tests — cover the `cars` tagging keywords and the non-empty default feed setting.
- No API, schema, migration, scheduler, or frontend changes. Existing already-ingested events are
  not retagged (tagging applies to newly created events); acceptable since this is the first
  configured source.
