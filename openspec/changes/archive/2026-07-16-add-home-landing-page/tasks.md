## 1. Backend: stories limit

- [x] 1.1 Add optional `limit` query param (ge=1) to `GET /api/v1/news/stories` in `app/api/news.py`, slicing the sorted story list in `app/news/stories.py` (or at the endpoint) after clustering
- [x] 1.2 Add API tests: `limit=5` returns the 5 newest-activity stories with the category map; omitted `limit` returns the full window

## 2. Frontend: widen news/events public surfaces

- [x] 2.1 Export `StoryCard`, the `Story` type, and a `setCategoryLabels()` helper from `frontend/src/features/news/index.ts`
- [x] 2.2 Export `EventCard` and the `EventItem` type from `frontend/src/features/events/index.ts`

## 3. Frontend: home feature

- [x] 3.1 Create `frontend/src/features/home/` with `state.svelte.ts` (stories, events, per-widget error flags) and `api.ts` fetching `/api/v1/news/stories?limit=5` and `/api/v1/events/items?limit=5` (no filter params), applying the fetched category labels via `setCategoryLabels()`
- [x] 3.2 Create `HomePage.svelte`: `.home-grid` of two `.widget` cards ("Latest news" reusing `StoryCard`, "Upcoming events" reusing `EventCard`), each with a heading, client-side "view all" link (`/news`, `/events`), independent inline error and empty states; export only `HomePage` from `index.ts`
- [x] 3.3 Add `frontend/src/styles/home.css` (auto-fit grid, widget card styles using theme variables) and import it from `main.ts`

## 4. Frontend: shell routing and nav

- [x] 4.1 Update `App.svelte` route table: `/` → `HomePage`, `/news` → `NewsFeed`; add "Home" nav link and point "News" at `/news`
- [x] 4.2 Update the 404 fallback copy and link to point to the home page

## 5. Verify

- [x] 5.1 Run backend tests and `svelte-check`; fix anything they surface
- [x] 5.2 Rebuild via `docker compose up --build` and manually verify: `/` shows both widgets (labels correct on a cold session, saved event filters ignored), `/news` renders the full feed, nav/back-forward work, unknown path links home
