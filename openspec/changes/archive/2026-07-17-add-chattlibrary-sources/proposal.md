# Add Chattanooga Public Library news and events sources

## Why

The Chattanooga Public Library is a major local institution missing from both aggregators: its
news page publishes announcements no registered outlet reliably carries, and its five-branch
events calendar runs 100+ events per two-week window (storytimes, career help, book clubs) —
exactly the kind of local happenings the events feature exists to surface. Both are freely
exposed by the library's WordPress site (verified 2026-07): a standard RSS category feed for
news, and The Events Calendar (tribe) REST API for events — no auth, no WAF, no spoofed
User-Agent required.

## What Changes

- Add **Chattanooga Public Library** as a seventh outlet in the news registry with the single
  feed `https://chattlibrary.org/category/news/feed/`, fallback category `life` (announcement
  volume is low, ~1–2 posts/month, and press-release-flavored like The Pulse's content).
- Add a **generic The Events Calendar (tribe) REST source** for the events feature: any
  WordPress site running The Events Calendar exposes
  `/wp-json/tribe/events/v1/events` with date-window filtering, pagination, venue objects
  (name + full postal address, sometimes coordinates), event images, and category names. The
  library's iCal export was rejected — it caps at 30 events (~6 days of this calendar vs. the
  14-day lookahead norm) and lacks images/categories.
- Register a default tribe calendar instance for `https://chattlibrary.org` (source name
  "Chattanooga Public Library"), configurable like the existing iCal feed list — overridable
  via environment, including to empty to disable.
- Out of scope: migrating the Cars and Coffee iCal feed onto the tribe source (its site runs
  the same plugin). Possible follow-up, deliberately not bundled here.

## Capabilities

### New Capabilities

None — both changes extend existing capabilities.

### Modified Capabilities

- `news`: the source/feed registry requirement grows from six outlets to seven (Chattanooga
  Public Library, single `life`-category feed). No behavior change to fetching, clustering, or
  categorization.
- `events`: new requirement for The Events Calendar (tribe) REST source — configured
  calendars, date-window pagination, field mapping (UTC times, venue name/address, supplied
  coordinates when present, image URL, category names as supplied tags), and offline-testable
  parsing. Sibling of the existing iCal / Meetup / CitySpark / CarCruiseFinder source
  requirements.

## Impact

- **Code**: `app/news/registry.py` (registry entry only); new `app/events/sources/tribe.py`;
  `app/events/sources/__init__.py` (wire configured tribe calendars); `app/config.py` (tribe
  calendar setting; lookahead reuses a setting aligned with CitySpark's 14-day norm).
- **Tests**: offline fixture-based parse tests for the tribe source (pattern: existing
  CitySpark/iCal tests); registry sync already covered generically.
- **Data/schema**: none — no migrations; events flow through the existing ingest
  (dedup/tagging/geocoding) pipeline; news feeds sync via the existing startup upsert.
- **Upstream dependencies**: chattlibrary.org availability; failures are contained by the
  existing per-feed (news) and per-source (events) error isolation.
