## Why

The Pulse — Chattanooga's arts & entertainment weekly, already ingested by the news feature as an
outlet — publishes the area's most comprehensive local events calendar at
`https://www.chattanoogapulse.com/local-events-calendar`. It is powered by CitySpark, and it dwarfs
what the events feature can see today: a 14-day window returns **526 events**, roughly an order of
magnitude more than all currently registered sources combined.

The calendar is not in the page's HTML (the server renders only Metro Publisher *article* teasers,
and the page's advertised `index.rss` is valid-but-empty — 0 items). It is a Vue widget injected
client-side, and it is backed by a clean JSON API that needs no auth, no referer, and no browser
User-Agent — a materially better footing than the `CarCruiseFinder` scraper, which must spoof a UA
past a Cloudflare WAF and parse HTML that can change shape at any time.

That payload also arrives **richer than the pipeline's source contract can carry**. Every event
(526/526) ships exact venue coordinates, and 520/526 ship real curated tags. Today `RawEvent`
deliberately carries "an address only, never coordinates", so ingest would discard those
coordinates and re-derive them through Nominatim at 1 request/second — roughly **8 minutes of
geocoding per cold cycle to rediscover, less accurately, what the payload already stated**. The
same holds for tags: keyword-guessing topics from title text when the source already states them.

## What Changes

- **BREAKING (internal convention, not API):** `RawEvent` gains optional `latitude`/`longitude`.
  This deliberately revises the documented "sources supply addresses, not coordinates" convention
  (`app/events/sources/base.py`, restated at `app/events/sources/meetup.py:9`). Ingest prefers
  source-supplied coordinates and geocodes only when they are absent.
- **BREAKING (internal convention, not API):** `RawEvent` gains an optional `tags` list. Ingest
  uses source-supplied tags when present and falls back to keyword tagging only when they are not.
- Both new fields are **optional**, so `ICalSource`, `MeetupSource`, and `CarCruiseFinderSource`
  are unchanged and keep their exact current behavior (geocode-from-address, keyword-tag).
- Add `CitySparkSource` (`app/events/sources/cityspark.py`), reading
  `POST https://portal.cityspark.com/api/events/GetEvents/ChattanoogaPulse`, registered in
  `build_sources()`. It supplies coordinates and tags, so it exercises both new fields.
- CitySpark ships tags as a **hierarchy** (`{id, name, parent}`, 23 roots, chains up to 5 deep). The
  source SHALL roll each of an event's tags up to **one level below its root** — `Live Music`
  (`Performing Arts > Music > Live Music`) becomes `music` — collapsing 250 leaf names to 95. This
  is what makes the vocabulary merge below actually work: `music` is the single most-used tag (280
  uses) and sits at exactly this level. Rolling all the way to the root instead would bury it in
  `performing arts` and merge with only 1 of the 11 keyword topics rather than 5.
- Source-supplied tag names are **lowercased on ingest**. Without this, CitySpark's `"Music"` would
  be stored beside keyword `"music"` as a separate row in the unique, case-sensitive `tags` table —
  fragmenting the vocabulary so `?topic=music` silently misses every CitySpark event. Five names
  collide this way: `family`, `food`, `music`, `nightlife`, `sports`.
- New settings for enablement, portal id/slug, radius, and lookahead window (`app/config.py`).
- Offline fixture-based tests; no network in tests.

## Capabilities

### New Capabilities

_None — this extends the existing `events` capability with a new source and a revised source
contract. Storage, API, scheduler, and frontend are untouched._

### Modified Capabilities

- `events`: three requirement changes plus one addition.
  - **Pluggable event source interface** — `RawEvent` may now carry coordinates and tags; the
    "an address only, never coordinates" constraint and its scenario are replaced by an explicit
    "sources may supply what they know; the pipeline derives the rest" rule, with the optional
    fields' backward compatibility pinned by scenario.
  - **Keyword topic tagging** — narrowed to a *fallback*: it applies only when the source supplies
    no tags. Adds the lowercase-normalization rule for supplied tags.
  - **Address geocoding with a permanent cache** — narrowed: ingest geocodes only events whose
    source supplied no coordinates.
  - **CitySpark events source** (new requirement) — the API contract, the mandatory
    `StartUTC`-over-`DateStart` rule, pagination, depth-1 tag rollup, and failure isolation.

## Impact

- **Code**: new `app/events/sources/cityspark.py`; `app/events/sources/base.py` (`RawEvent` fields);
  `app/events/ingest.py` (prefer supplied coords/tags); `app/events/sources/__init__.py`
  (registration); `app/config.py` (settings); new tests + fixture.
- **Not changed**: models, migrations, API routes, scheduler, frontend. The `tags` table is already
  a free-text vocabulary (`name String(64) unique`, max observed CitySpark name is 24 chars), so no
  migration is needed.
- **Data volume**: CitySpark will dominate the events table (~526 events per 14-day window). Ingest
  cycle cost shifts from geocoding to de-duplication — and because this source supplies
  coordinates, the largest source in the system adds **~zero Nominatim traffic**.
- **De-duplication**: CitySpark is an aggregator-of-aggregators (it carries chattanooga library and
  Bandsintown listings, among others), so it *will* overlap the existing Meetup and iCal sources.
  This is expected and handled by existing cross-source dedup — and improved by it, since
  `dedup.events_match` gates merges on location and CitySpark supplies exact coordinates.
- **Systems / external — known risk**: this is an **undocumented internal endpoint** of a
  commercial aggregator, read via The Pulse's portal id (`ppid 9824`). It may change or be
  restricted without notice. Request volume is minimal (a handful of paged POSTs per refresh) and
  no protection is circumvented — unlike CarCruiseFinder, nothing needs spoofing. Breakage
  manifests as zero events plus logs, contained by `run_sources()`'s existing per-source failure
  isolation. Recorded here in the same spirit as the CarCruiseFinder source's honesty about its own
  fragility.
- **Follow-up (out of scope)**: `MeetupSource` could request coordinates in its GraphQL `venue {}`
  selection and drop its geocoding entirely via the same new field. Not done here.
