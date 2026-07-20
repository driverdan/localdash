## 1. Fixtures

- [x] 1.1 Add `tests/fixtures/chattzoo/listing.html` — a trimmed capture of
      `https://chattzoo.org/events/zooevents` retaining the `a.col.third.fundraiser` cards
      (detail href, card `<img>`, `<h2>` title) for several events
- [x] 1.2 Add `tests/fixtures/chattzoo/detail_multi.html` — an Adventure Days-style capture with
      four `.event-logo h5 > span` occurrences, one of which is stale/past
- [x] 1.3 Add `tests/fixtures/chattzoo/detail_single.html` — a Pirates-style capture with one
      occurrence and a description
- [x] 1.4 Add `tests/fixtures/chattzoo/detail_unparseable.html` — a capture whose occurrence
      spans include one malformed date string alongside a valid one

## 2. Date resolution

- [x] 2.1 Create `app/events/sources/chattzoo.py` with the module docstring recording why this
      source fetches detail pages (the listing has no dates) and why that does not contradict
      the CarCruiseFinder listing-only rule (that site's detail pages carry wrong UTC offsets;
      the zoo's carry none)
- [x] 2.2 Implement a pure occurrence parser that turns `March 22 | 9:00 AM - 5:00 PM` into a
      month/day plus start and end times, returning `None` for unparseable strings
- [x] 2.3 Implement pure year resolution: choose among previous/current/next calendar year the
      candidate date nearest to a passed-in reference date (reference passed explicitly so
      tests are deterministic)
- [x] 2.4 Interpret resolved times as America/New_York and convert to timezone-aware UTC start
      and end times
- [x] 2.5 Drop occurrences whose resolved end time is already past

## 3. Parsing

- [x] 3.1 Implement pure `parse_listing(html, listing_url)` returning title, image URL, and
      absolute detail URL per card, de-duplicating repeated detail URLs
- [x] 3.2 Implement pure `parse_detail(html, url, title, image_url, now)` returning one
      `RawEvent` per surviving occurrence
- [x] 3.3 Set `source_event_id` to `<page slug>#<YYYY-MM-DD>` so occurrences stay distinct
      through ingest's exact source-listing dedup tier
- [x] 3.4 Supply the zoo venue name, full postal address (301 North Holtzclaw Avenue,
      Chattanooga, TN 37404), and fixed latitude/longitude as module constants on every event
- [x] 3.5 Run image URLs through `clean_image_url` and leave `tags` empty for the keyword tagger

## 4. Source class and registration

- [x] 4.1 Implement `ChattZooSource(EventSource)` with an injectable listing URL and timeout,
      fetching with the project's standard `user_agent` and `follow_redirects=True`
- [x] 4.2 Fetch detail pages sequentially, catching per-page failures so one bad page logs a
      warning and skips only its own event
- [x] 4.3 Register `ChattZooSource()` unconditionally in `build_sources()`
      (`app/events/sources/__init__.py`) alongside `CarCruiseFinderSource()`, and export it
      from the package

## 5. Tests

- [x] 5.1 Add `tests/test_events_chattzoo.py` covering `parse_listing`: cards become
      title/image/detail-URL triples, and a listing with no cards yields nothing
- [x] 5.2 Test year resolution directly at a pinned reference date: `December 20` at
      2026-07-20 → 2026; `March 22` at 2026-07-20 → 2026 and dropped as past (assert no 2027
      event is produced); `January 10` at 2026-12-20 → 2027
- [x] 5.3 Test fan-out: the multi-date fixture yields one event per upcoming occurrence,
      sharing title/description/image/URL and differing in start time and `source_event_id`
- [x] 5.4 Test that a fixture whose dates are all past yields zero events
- [x] 5.5 Test that an unparseable occurrence is skipped while its siblings still parse
- [x] 5.6 Test that every produced event carries the zoo's coordinates, so ingest would not
      geocode it
- [x] 5.7 Test source-level failure isolation: a failing listing fetch yields zero events
      without raising, and a failing detail fetch loses only that event

## 6. Documentation

- [x] 6.1 Add the zoo source to the events-source inventory in `AGENTS.md`
- [x] 6.2 Add to the "Events source gotchas" list in `AGENTS.md`: the year-less dates and the
      nearest-year-then-drop-past rule, why past occurrences are never rolled forward, and why
      this source fetches detail pages when CarCruiseFinder must not

## 7. Verification

- [x] 7.1 Run the test suite and the project's lint/format/type checks
- [x] 7.2 Rebuild with `docker compose up --build` and confirm zoo events appear on `/events`
      with correct dates, images, and links
