## 1. Pipeline plumbing (model, migration, RawEvent)

- [x] 1.1 Add optional `image_url: str | None = None` to `RawEvent` and a shared placeholder-exclusion helper in `app/events/sources/base.py` (case-insensitive generic/placeholder/default/stock basename pattern → treat URL as absent)
- [x] 1.2 Add nullable `image_url` Text column to `Event` in `app/events/models.py` and create the Alembic migration (plain column add, no backfill)
- [x] 1.3 Ingest (`app/events/ingest.py`): set `image_url` on newly created events; add null-only backfill to the merge path in `upsert_raw_events` and to `_merge_pair`; extend `tests/test_events_ingest.py` (new-event set, merge backfill, never-overwrite)

## 2. Sources

- [x] 2.1 CitySpark (`cityspark.py`): supply `image_url` from `MediumImg` with `LargeImg` → `SmallImg` → first `Images[].url` fallback, through the placeholder helper; extend `tests/test_events_cityspark.py`
- [x] 2.2 CarCruiseFinder (`carcruisefinder.py`): supply `image_url` from the JSON-LD `image` property (string or list form), through the placeholder helper; extend `tests/test_events_carcruisefinder.py`
- [x] 2.3 iCal (`ical.py`): supply `image_url` from an image `ATTACH` property, through the placeholder helper (the Cars and Coffee `Generic-*.jpg` stock images must come out as no image); extend `tests/test_events_ical.py`
- [x] 2.4 Meetup (`meetup.py`): add the event photo to the GraphQL selection (verify exact field — `featuredEventPhoto` vs. `images` — against the live schema; parse defensively so a missing photo yields null), through the placeholder helper; extend `tests/test_events_meetup.py`

## 3. API

- [x] 3.1 Serialize `image_url` in `_serialize` in `app/api/events.py`; extend `tests/test_api_events.py` (URL present and null cases)

## 4. Frontend

- [x] 4.1 Add `image_url: string | null` to the event type in `frontend/src/features/events/types.ts`
- [x] 4.2 Render the conditional lead image in `EventCard.svelte` (`{#if event.image_url}`, `loading="lazy"`, empty alt), styled per the `StoryCard.svelte` pattern; no reserved space when absent

## 5. Verify

- [x] 5.1 Run backend tests, `svelte-check`/frontend build, and rebuild via `docker compose up --build`; confirm event cards show images after a refresh and imageless events render unchanged
