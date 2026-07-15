## Why

Story cards render as text-only, which is visually flat for a news homepage. Several outlets already
ship an image in their RSS feed (Local 3 in nearly every item, WDEF occasionally); we throw that data
away today. Capturing it lets cards show a lead image at essentially no new network cost.

## What Changes

- Store an optional `image_url` on articles: parse the first image `enclosure`, falling back to the
  first `<img>` in the item's content/summary HTML.
- Surface an image on each story by borrowing it from the story's first-by-published member that has
  one (consistent with how the headline comes from the earliest article).
- Add `image_url` to the stories API payload and the frontend `Story` type.
- Render the image on `StoryCard` when present; stories without one render exactly as today
  (no placeholder).
- Scope is feed-supplied images only — no fetching of article pages / `og:image` scraping.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `news`: article storage gains an optional feed-supplied `image_url`; the stories API returns a
  per-story image chosen from the earliest member that carries one.
- `frontend-news`: story cards render a feed-supplied image when present, with no placeholder
  otherwise.

## Impact

- **Schema/migration**: new nullable `image_url` column on `news_articles` (new Alembic revision).
- **Backend**: `app/news/fetcher.py` (parse image), `app/news/models.py` (column),
  `app/news/stories.py` (`build_stories`/`get_stories` select + emit), `app/api/news.py` (payload).
- **Frontend**: `frontend/src/features/news/types.ts` (`Story.image_url`),
  `StoryCard.svelte` (render), `frontend/src/styles/news.css` (image styling).
- No new dependencies; no extra HTTP requests per refresh cycle.
