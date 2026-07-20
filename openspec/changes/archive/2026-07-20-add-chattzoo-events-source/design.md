## Context

The Chattanooga Zoo publishes events at `https://chattzoo.org/events/zooevents` on a Craft CMS
site with hand-written Twig templates. Reconnaissance established the constraints this design
has to work within:

- **No machine endpoint exists.** `/events/zooevents.ics`, `/events/feed`, `/api`,
  `/actions/element-api`, `/events.rss`, and `/sitemap.xml` all return 404. The markup carries
  no JSON-LD, no microdata, and no Open Graph tags. Scraping is the only route.
- **The listing page has no dates.** Each event is an `<a class="col third fundraiser">`
  wrapping a card with an `<img>` and an `<h2>` title, linking to a detail page. Dates,
  times, and descriptions appear only on the detail page, inside `<span>` elements under
  `.event-logo h5`.
- **Dates carry no year.** The detail pages render occurrences as free text —
  `March 22 | 9:00 AM - 5:00 PM` — with the year nowhere in the markup.
- **Detail pages list multiple occurrences.** Adventure Days lists four dates (March 22,
  June 28, September 20, December 20); Homeschool Days lists two; Pirates, Parrots &
  Princesses lists one.
- **Stale occurrences are retained.** As of reconnaissance (July 2026), Adventure Days still
  listed its March 22 date, four months past.
- **The site is visibly under-maintained.** An unclosed Twig comment
  (`<!-- |sort((a) => a.eventDates.one()) -->`) leaks into the listing HTML, and 404s render a
  full Craft/Yii stack trace, indicating the site runs with dev mode on.
- Every event happens at one address: 301 North Holtzclaw Avenue, Chattanooga, TN 37404.

The existing pipeline (`fetch sources → ingest → serve`) needs no changes. `RawEvent` already
carries every field this source can supply, and `run_sources()` already isolates per-source
failures.

## Goals / Non-Goals

**Goals:**

- Surface upcoming Chattanooga Zoo events on `/events` with correct start and end times,
  titles, descriptions, images, and links back to the zoo's own pages.
- Never emit an event with a fabricated or wrong date — a wrong timestamp silently corrupts
  `canonical_key` and breaks cross-source de-duplication, the failure mode AGENTS.md already
  records twice (CitySpark's fake `Z` suffix, CarCruiseFinder's wrong detail-page offsets).
- Add zero geocoder load.
- Keep parsing pure and offline-testable against fixtures, so the inevitable markup change is
  caught by a failing test rather than by silence in production.

**Non-Goals:**

- The zoo's **Daily Schedule** page (keeper talks, feedings). That is recurring daily
  programming, not discrete dated events, and does not fit the events model.
- Ticket prices, member-vs-public pricing tiers, and sponsor blocks on the detail pages.
- Any generalized "Craft CMS source" abstraction. This is one bespoke site.
- Recovering the events that are past. Only upcoming occurrences are ingested.

## Decisions

### Two-hop fetch (listing → detail pages)

The listing page carries no dates, so an event cannot be constructed from it alone. The source
fetches the listing, extracts the detail URLs, and fetches each detail page.

This deliberately breaks `CarCruiseFinderSource`'s "listing page only" rule. That rule exists
for a specific reason — CarCruiseFinder's detail pages carry **wrong UTC offsets** (EST on
August dates), which would corrupt canonical keys. The zoo's detail pages carry no offsets at
all, so the hazard does not transfer. The reason is recorded in the module docstring so the two
rules are not confused later.

Volume is small (currently 4 detail pages) and the refresh interval is 60 minutes, so the
requests are fetched sequentially with no added rate limiting. A detail-page failure is caught
per page: that event is skipped and the remaining pages still produce events.

*Alternative considered:* parse dates from the listing page. Rejected — they are not there.

### Year resolution: nearest year, then drop past

For a parsed month/day, evaluate the candidate dates in the previous, current, and next
calendar year, and choose whichever lands closest to today. Then discard any occurrence whose
end time is already past.

| Text | Today | Candidates | Chosen | Outcome |
|---|---|---|---|---|
| `March 22` | 2026-07-20 | −120d / +245d | 2026 | dropped (past) |
| `December 20` | 2026-07-20 | +153d | 2026 | kept |
| `January 10` | 2026-12-20 | −344d / +21d | **2027** | kept |

This is a single rule with no tuned thresholds, and it is the only candidate that handles the
December→January rollover correctly while refusing to invent a future occurrence out of a
stale past one.

*Alternatives considered:*

- **Always assume the current year.** Simple, but in late December a page advertising a
  January event yields a date eleven months in the past, which is then dropped — the event
  silently disappears exactly when it is most imminent.
- **Always roll forward to the next future occurrence.** Turns the stale `March 22` entry into
  a fictional March 2027 event. Fabricating events is the worst available failure.
- **Scrape the year out of the description prose.** Homeschool Days does happen to say
  "September 4 and 11, 2026" in its body copy, but Adventure Days and Pirates do not. Too
  unreliable to depend on, and it fails silently.

The rule is wrong for anything published more than roughly six months ahead. That is an
accepted limitation, stated explicitly in the module docstring alongside the other source
gotchas.

### Fan out occurrences, with per-occurrence source event ids

One detail page yields *N* `RawEvent`s, one per `<span>` occurrence that survives the past
filter. All share the page's title, description, image, and URL.

`source_event_id` must therefore be `<slug>#<YYYY-MM-DD>`, not the slug alone — otherwise the
four Adventure Days occurrences collapse to one on ingest's exact source-listing dedup tier.

`canonical_key` needs no special handling: it already hashes normalized title plus start hour,
so the occurrences differ naturally.

### Supply venue coordinates, do not geocode

Every zoo event is at the same address. The source supplies `venue_name`, the full `address`
string, and hardcoded `latitude`/`longitude` for 301 N Holtzclaw Ave. Ingest geocodes only
events without coordinates, so the zoo adds nothing to the Nominatim budget — the same
approach CitySpark takes.

The address is still supplied even though coordinates are present, because it is displayed in
the UI and used by the de-duplication location gate.

### Registered unconditionally, no config

The source is registered in `build_sources()` with no enable flag and no settings, exactly as
`CarCruiseFinderSource` is. The config-driven sources (`ICalSource`, `TribeEventsSource`,
`MeetupSource`) are parameterized because they are *classes* of source with swappable targets;
the zoo is a single hardcoded site, so a setting would be dead configuration.

The listing URL stays a module constant, injectable via the constructor for tests.

### Fetch etiquette

Requests send the project's standard `user_agent`. Unlike CarCruiseFinder, the zoo site does
not require a browser User-Agent — plain requests succeed — so no UA spoofing is introduced.
The listing is served from the apex domain and links to `www.`, so redirects are followed.

### Tagging

The source supplies no tags; ingest's keyword tagger derives them from title and description,
which is the existing default for every source except CitySpark. The recently added tag
blocklist applies unchanged.

## Risks / Trade-offs

- **Markup changes break parsing silently** → Parsing lives in pure `parse_listing` /
  `parse_detail` functions tested against committed fixtures, so a structural change is caught
  by a failing test. In production, breakage yields zero zoo events plus a warning log,
  contained by `run_sources()`'s per-source isolation — never a failed refresh cycle.

- **Year inference is wrong for events published far ahead** → Accepted, bounded, and
  documented. The rule fails toward dropping an event, never toward inventing one.

- **Stale occurrences left on the pages could resurface** → The past filter runs on every
  cycle against the current time, so a stale date is dropped every time rather than once.

- **Adventure Days is co-hosted with the Chattanooga Public Library**, already ingested via
  `TribeEventsSource` → If the library lists it too, the fuzzy dedup tier merges only when the
  locations agree within 0.5 miles. A library-addressed listing would not merge, producing a
  visible duplicate. Accepted for now: the zoo supplies real coordinates, so a
  correctly-addressed library listing *will* merge, and a visible duplicate is a cosmetic
  issue rather than a data-integrity one.

- **The site runs Craft in dev mode and leaks stack traces** → Not something this change can
  or should exploit; the source reads only the two public page types and treats any non-200 as
  a skip.

- **Detail-page fetches multiply request count** → Bounded by the number of listed events
  (currently 4) at a 60-minute interval. If the listing ever grows unexpectedly large, the
  per-cycle cost grows linearly; a cap is not worth adding preemptively for a venue that runs
  a handful of events at a time.
