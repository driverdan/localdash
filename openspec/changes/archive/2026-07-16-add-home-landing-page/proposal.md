## Why

The root route currently drops visitors straight into the news feed, so the other features (events, map) and any future at-a-glance data have no shared front door. A dedicated landing page gives the dashboard an actual "dashboard" view: a quick digest of the latest news and upcoming events, with room to grow into weather, timeseries summaries, and other widgets.

## What Changes

- **BREAKING (route)**: The news feed moves from `/` to `/news`. `/` becomes a new home/landing page.
- New `features/home` frontend feature renders a widget grid with two cards:
  - **Latest news** — the 5 newest stories, reusing `StoryCard`, with a "view all" link to `/news`.
  - **Upcoming events** — the next 5 upcoming events, reusing `EventCard`, with a "view all" link to `/events`.
- The home page fetches its own data with its own slim state; it ignores the user's persisted event topic/distance filters and news category/hours preferences.
- `/api/v1/news/stories` gains an optional `limit` query parameter so the home fetch stays small (stories remain sorted newest-first).
- Nav gains a **Home** link at `/`; the **News** link points to `/news`. The 404 fallback copy/link is updated to point home.
- The widget grid layout is designed so future cards (weather, timeseries summary) can be added without restructuring.

## Capabilities

### New Capabilities
- `frontend-home`: Landing page feature at `/` — widget grid composing digest cards (latest news, upcoming events) with independent, unfiltered data fetches and links into the full feature pages.

### Modified Capabilities
- `frontend-shell`: Client-side path routing — route table changes: `/` renders home, `/news` renders the news feed; nav and 404 fallback updated.
- `frontend-news`: News feed renders at `/news` instead of `/` (route move only; feed behavior unchanged).
- `news`: Stories API accepts an optional `limit` parameter bounding the number of stories returned.

## Impact

- **Frontend**: new `frontend/src/features/home/` namespace (state, api, components); `App.svelte` route table and nav; `lib/router` untouched; a new `styles/home.css` (or grid rules in an existing global sheet) per the styling contract.
- **Backend**: `app/api/news.py` `get_stories` endpoint and `app/news/stories.py` gain a `limit`; events API already supports `limit` — no change.
- **Tests**: `tests/test_api_routes.py` (or news API tests) for the stories `limit`; frontend type-check via `svelte-check`.
- **Users**: bookmarks to `/` now land on the home page; news is one click away under the new nav item.
