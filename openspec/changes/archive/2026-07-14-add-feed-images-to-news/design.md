## Context

Story cards are text-only. Probing the four live feeds shows uneven image availability: Local 3
(TownNews) ships an image `enclosure` on ~9/10 items, WDEF (WordPress) has an inline `<img>` in item
content on ~1/10, and Chattanoogan and Times Free Press carry no image markup at all. The fetcher
(`app/news/fetcher.py`) currently reads only link/title/guid/summary and discards everything else.

Because the UI renders clustered *stories*, not raw articles, image coverage at the story level is
better than the per-outlet numbers suggest: a story can borrow an image from any member article, so
a Times Free Press / Chattanoogan story that clusters with a Local 3 article gets an image.

## Goals / Non-Goals

**Goals:**
- Capture a feed-supplied image per article with no extra network calls in the refresh cycle.
- Give each story a single lead image chosen deterministically from its members.
- Render it on `StoryCard` with graceful, placeholder-free absence.

**Non-Goals:**
- No fetching of article pages or scraping `og:image` / `twitter:image`.
- No image proxying, resizing, caching, or rehosting — the feed's URL is used as-is.
- No placeholder art for imageless stories.

## Decisions

**Image extraction: enclosure first, inline `<img>` fallback.**
feedparser exposes image `enclosure`s at `entry.enclosures` (filter `type` starting `image`) and
`entry.media_content` / `media_thumbnail` for Media RSS. In the probed feeds the reliable structured
source is the image `enclosure` (Local 3); WDEF only has an `<img>` inside content HTML. So the
fetcher takes the first image enclosure, else the first `<img src=...>` found in the content/summary
HTML (the same raw HTML `_entry_summary` already handles, before `strip_html`). `media:content`/
`media:thumbnail` are not present in these feeds; if cheap to include they can be folded into the
enclosure step, but they are not required. Store `None` when neither is found.
- *Alternative — parse `og:image` per article:* better/uniform coverage but adds an HTTP GET + HTML
  parse per article (and the TownNews 429 UA hazard). Explicitly out of scope for this change.

**Story image: earliest member that has one.**
Members are already ordered by `published` ascending in `get_stories`, and `build_stories` uses
`members[0]` for the headline. The story image is the first member in that order whose `image_url`
is non-null — consistent with "headline from the earliest report." Deterministic, no ranking logic.
- *Alternative — prefer the highest-quality/enclosure image, or most recent:* more machinery for
  marginal benefit; first-by-published matches the existing headline rule and is trivial to reason
  about.

**Schema: one nullable `Text` column `image_url` on `news_articles`.**
No new table, no backfill. A raw-SQL Alembic revision `ALTER TABLE ... ADD COLUMN image_url text`
matching the hand-written-SQL migration style. Existing rows stay null until re-fetched; the upsert
path naturally populates them on the next cycle.

**API + frontend contract.**
`stories.py` adds `image_url` to the row select and emits it on each story dict; the FastAPI
response model / serializer in `app/api/news.py` passes it through. `types.ts` adds
`image_url: string | null` to `Story`. `StoryCard.svelte` renders `<img>` only when truthy; styling
lives in the global `news.css` per the styling contract (no scoped `<style>` block).

## Risks / Trade-offs

- **Uneven coverage** → accepted. Only Local 3 (and occasional WDEF) items carry images, so
  single-source Chattanoogan/TFP stories stay text-only. Clustering lifts multi-source coverage; the
  placeholder-free design makes mixed cards look intentional.
- **Hotlinking third-party image URLs** → the feed's own CDN (e.g. TownNews `bloximages`) serves
  them; we display the outlet's image as-is, same trust boundary as linking the article. A broken or
  slow image URL degrades to no image; markup should not reserve space or break layout on load
  failure.
- **Inline `<img>` may be a tracking pixel / tiny asset** → low risk in these feeds, but the fallback
  should take the first `<img>` in article content, not decorative markup; acceptable for v1 given
  WDEF's low volume. Revisit only if bad images show up.
- **Dimensions unknown** → feed images have no guaranteed size; CSS must constrain them (max-width,
  fixed aspect via object-fit) so a large or oddly-shaped image can't blow out the card.

## Migration Plan

1. Add the Alembic revision (additive, nullable column) — safe to apply live, no backfill.
2. Deploy backend; next refresh cycle populates `image_url` for image-bearing items.
3. Frontend renders images as stories acquire them. Rollback is dropping the column (or ignoring it);
   no data migration to reverse.
