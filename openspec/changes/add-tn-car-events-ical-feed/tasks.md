# Tasks: add-tn-car-events-ical-feed

## 1. Config default

- [ ] 1.1 In `app/config.py`, change the `events_ical_feeds` default from `""` to
      `"https://carsandcoffeeevents.com/events/category/tennessee/?ical=1"` (keep the
      comma-separated-URLs comment accurate).
- [ ] 1.2 In `.env.example`, update the `EVENTS_ICAL_FEEDS=` line to show the new default value
      and add a brief comment noting it is the shipped default (set empty to disable, or list
      other feeds to replace it).

## 2. Cars topic tagging

- [ ] 2.1 In `app/events/tagging.py`, add a `"cars"` entry to `TOPIC_KEYWORDS` with keywords:
      `"car show"`, `"cruise-in"`, `"cruise in"`, `"cars and coffee"`, `"car meet"`,
      `"hot rod"`, `"classic car"`, `"corvette"`, `"mustang"`, `"camaro"`, `"auto show"`
      (no bare `"car"` keyword).

## 3. Tests

- [ ] 3.1 In `tests/test_events_tagging.py`, add cases: "Ooltewah Cruise In @ Cambridge Square"
      → `{"cars"}`; a "Cars and Coffee" title → tagged `cars`; "Downtown Carnival" → not tagged
      `cars`.
- [ ] 3.2 Add a source-registry test (alongside the `build_sources` coverage in
      `tests/test_events_meetup.py` or a more fitting module): default `Settings()` yields
      exactly one `ICalSource` for the carsandcoffeeevents.com Tennessee URL, and
      `events_ical_feeds=""` yields no iCal sources.
- [ ] 3.3 Run `pytest` — full suite green (DB-backed tests may auto-skip without Postgres).

## 4. Verify and sync

- [ ] 4.1 Run the stack (`sg docker -c 'docker compose up --build'`) and confirm a refresh cycle
      ingests the feed: `GET /api/v1/events/items?topic=cars` returns car events, and Chattanooga-
      metro entries (e.g. Ooltewah Cruise In) appear within `max_miles=25` of the default origin.
- [ ] 4.2 Confirm the `cars` chip appears on `/events` (tags come from `GET /api/v1/events/tags`
      dynamically — no frontend change expected).
