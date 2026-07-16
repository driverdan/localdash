## Why

Most event sources already ship a per-event image in payloads we fetch today (verified live: CitySpark populates image URLs on 100% of sampled events, CarCruiseFinder's JSON-LD carries `image` on every listing, Meetup's GraphQL schema exposes event photos), but the pipeline never parses them — event cards are text-only while news cards show a lead image. Surfacing the image makes the events list scannable the same way the news feed is, at no extra fetch cost.

## What Changes

- `RawEvent` gains an optional `image_url` field; each source supplies it when the upstream payload has a usable image:
  - **CitySpark**: `MediumImg` (pre-sized card variant).
  - **CarCruiseFinder**: the JSON-LD `image` property.
  - **Meetup**: event photo added to the GraphQL selection.
  - **iCal**: `ATTACH` image — but known generic/placeholder images are ignored (the configured Cars and Coffee feed only ships stock images like `Generic-Car-Show.jpg`).
- `Event` gains a nullable `image_url` column (Alembic migration), following the `NewsArticle.image_url` precedent.
- Ingest sets the image on new events and backfills it on merge, using the existing null-backfill pattern (first source to supply one wins).
- The events listing API serializes `image_url`.
- `EventCard` renders the image when present, mirroring `StoryCard`'s conditional lead image.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `events`: the source interface (`RawEvent`), each source requirement (CitySpark, CarCruiseFinder, Meetup, iCal), de-duplication merge backfill, event storage, and the listing API all gain the optional event image; generic/placeholder upstream images are excluded at parse time.
- `frontend-events`: the event list requirement gains conditional lead-image rendering on event cards.

## Impact

- **Backend**: `app/events/sources/base.py` (RawEvent), `cityspark.py`, `carcruisefinder.py`, `meetup.py`, `ical.py` (parse image), `app/events/models.py` + new Alembic migration (column), `app/events/ingest.py` (create + merge backfill), `app/api/events.py` (serialize).
- **Frontend**: `frontend/src/features/events/components/EventCard.svelte`, `frontend/src/features/events/types.ts` (or equivalent event type), styling per the existing StoryCard image pattern.
- **Data**: images are hotlinked third-party URLs (Azure blob storage, WordPress uploads) exactly like news images today; nothing is downloaded or stored locally. Existing rows stay null until the next refresh re-reports them.
- **Dependencies**: none added.
