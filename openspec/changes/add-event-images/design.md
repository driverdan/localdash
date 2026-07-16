## Context

Event cards are text-only while news cards show a feed-supplied lead image (`NewsArticle.image_url`, rendered conditionally by `StoryCard.svelte`). The event pipeline already fetches payloads that contain per-event images; it just never parses them. Verified live (2026-07-16):

- **CitySpark** (`GetEvents` JSON): `SmallImg`/`MediumImg`/`LargeImg` pre-sized URL variants on Azure blob storage, populated on 89/89 sampled events (77 distinct URLs; repeats are recurring events sharing their own artwork, not placeholders).
- **CarCruiseFinder** (listing-page JSON-LD): schema.org `image` on 19/19 events.
- **iCal / Cars and Coffee**: `ATTACH;FMTTYPE=image/jpeg` present, but every value is a stock image (`Generic-Cruise-Night.jpg`, `Generic-Car-Show.jpg`).
- **Meetup** (GraphQL, token-gated): the `Event` type exposes event photos; the current selection simply doesn't request them.

Events are de-duplicated across sources, so one canonical `Event` may receive images from several origins; ingest already resolves such conflicts for description/venue/address/end-time with a null-only backfill.

## Goals / Non-Goals

**Goals:**

- Store at most one image URL per canonical event and render it on the event card when present.
- Supply the image from every source whose upstream data has a real per-event image.
- Never surface generic/placeholder stock images.
- Follow the news feature's existing shape (single nullable URL column, hotlinked; conditional `<img>` in the card).

**Non-Goals:**

- Downloading, caching, resizing, or proxying images locally — images are hotlinked third-party URLs exactly like news images.
- Multiple images per event, size variants, or art direction (`srcset`).
- Backfilling images into past events; rows populate as refresh cycles re-report events.
- Filtering by image or any image-based UI beyond the card thumbnail.

## Decisions

**One nullable `image_url` Text column, mirroring news.** `NewsArticle.image_url` is the established precedent: a single feed-supplied URL, nullable, hotlinked. Storing CitySpark's three size variants (or the `Images` array) would complicate the schema for no consumer — the card needs one URL. Alternative considered: a JSON column of variants; rejected as speculative.

**CitySpark supplies `MediumImg`.** The card thumbnail is small; `MediumImg` is the purpose-built middle variant. `LargeImg` wastes bandwidth on a card, `SmallImg` risks visible upscaling. Fallback chain (`MediumImg` → `LargeImg` → `SmallImg` → first `Images[].url`) guards against a partially populated payload.

**Placeholder exclusion happens at source parse time, by filename heuristic.** A source is where format knowledge lives (same reason each source owns its time-field quirks). An ATTACH/image URL whose basename matches a case-insensitive `generic`/`placeholder`/`default`/`stock` pattern is treated as absent. This is deliberately a heuristic: it exactly covers the observed Cars and Coffee stock images (`Generic-*.jpg`) and costs nothing when it misses — a missed placeholder just renders a bland but topical image. The helper lives in `sources/base.py` so every source (current and future) applies the same rule. Alternative considered: dropping iCal ATTACH support entirely; rejected because future feeds may ship real images and the requirement is about *placeholders*, not iCal.

**Merge semantics: null-only backfill, first image wins.** New events take the raw image directly; the merge path in `upsert_raw_events` and `_merge_pair` in `reconcile_events` backfill `image_url` only when the stored value is null, identical to description/venue/address/end-time. No source-priority ranking — CitySpark's near-total coverage makes ordering moot in practice, and the existing backfill pattern is already the codebase's answer to this conflict. This also gives existing rows images organically: the next refresh re-reports each upcoming event, tier-1 matches it, and the backfill fills the null.

**Meetup: add the photo to the GraphQL selection; verify the exact field name at implementation time.** The source only runs when an OAuth token is configured, so the exact field (`featuredEventPhoto` vs. `images`) is confirmed against the live schema during implementation; parse defensively (missing photo → null) either way.

**Migration is a plain nullable column addition.** No data backfill, no default. Rollback is dropping the column.

**Frontend mirrors `StoryCard`.** `EventCard.svelte` gets a conditional `<img loading="lazy">` behind `{#if event.image_url}`, with empty `alt` (decorative — the title is adjacent text) and styling consistent with the card layout; the event TypeScript type gains `image_url: string | null`.

## Risks / Trade-offs

- [Hotlink rot / third-party WAFs] An upstream host may 404, block, or rate-limit direct image loads. → Same exposure the news feature has carried since launch; a broken image is contained to one card (`<img>` renders nothing on error, optionally hidden via error handler). Nothing is stored locally, so stale URLs cost nothing.
- [Filename heuristic misses a placeholder] A feed could ship a stock image without a telltale name. → Accepted: the cost is a bland image, not incorrect data; the blocklist pattern is a one-line change when a new placeholder is observed.
- [Heuristic false positive] A real image whose filename contains "generic" would be dropped. → Accepted: the event just renders text-only, the pre-image status quo.
- [CitySpark payload drift] `MediumImg` could vanish in the undocumented API. → The fallback chain plus null-tolerance means drift degrades to imageless events, the existing breakage mode for this source.
- [Stored image outlives its listing] A source may replace an event's artwork; null-only backfill never updates a non-null value. → Accepted for parity with description/venue backfill; events are short-lived rows.

## Open Questions

None — the Meetup field-name check is folded into implementation since it needs a configured token.
