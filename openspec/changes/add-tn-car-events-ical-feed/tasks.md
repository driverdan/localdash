# Tasks: add-tn-car-events-ical-feed

## 1. Config default

- [x] 1.1 In `app/config.py`, change the `events_ical_feeds` default from `""` to
      `"https://carsandcoffeeevents.com/events/category/tennessee/?ical=1"` (keep the
      comma-separated-URLs comment accurate).
- [x] 1.2 In `.env.example`, update the `EVENTS_ICAL_FEEDS=` line to show the new default value
      and add a brief comment noting it is the shipped default (set empty to disable, or list
      other feeds to replace it).

## 2. Cars topic tagging

- [x] 2.1 In `app/events/tagging.py`, add a `"cars"` entry to `TOPIC_KEYWORDS` with keywords:
      `"car show"`, `"cruise-in"`, `"cruise in"`, `"cars and coffee"`, `"car meet"`,
      `"hot rod"`, `"classic car"`, `"corvette"`, `"mustang"`, `"camaro"`, `"auto show"`
      (no bare `"car"` keyword).

## 3. Tests

- [x] 3.1 In `tests/test_events_tagging.py`, add cases: "Ooltewah Cruise In @ Cambridge Square"
      → `{"cars"}`; a "Cars and Coffee" title → tagged `cars`; "Downtown Carnival" → not tagged
      `cars`.
- [x] 3.2 Add a source-registry test (alongside the `build_sources` coverage in
      `tests/test_events_meetup.py` or a more fitting module): default `Settings()` yields
      exactly one `ICalSource` for the carsandcoffeeevents.com Tennessee URL, and
      `events_ical_feeds=""` yields no iCal sources.
- [x] 3.3 Run `pytest` — full suite green (DB-backed tests may auto-skip without Postgres).

## 4. Verify and sync

- [x] 4.1 Run the stack (`sg docker -c 'docker compose up --build'`) and confirm a refresh cycle
      ingests the feed: `GET /api/v1/events/items?topic=cars` returns car events, and Chattanooga-
      metro entries (e.g. Ooltewah Cruise In) appear within `max_miles=25` of the default origin.
      (Verified: feed fetched HTTP 200, 30 events ingested, `topic=cars` returns 25 events
      including "Ooltewah Cruise In @ Cambridge Square" with geocodable street address
      `9452 Bradmore Ln, Ooltewah, TN 37363`. The `max_miles=25` distance filter returns 0 only
      because Nominatim is currently 429-rate-limiting this host's IP, so addresses haven't
      resolved to coordinates yet — an external-service throttle, not a change defect; the
      permanent geocode cache will populate once Nominatim recovers.)
- [x] 4.2 Confirm the `cars` chip appears on `/events` (tags come from `GET /api/v1/events/tags`
      dynamically — no frontend change expected). (Verified: `GET /api/v1/events/tags` returns
      `cars` in its tag list.)
