## Why

LocalDash currently surfaces only geolocation time-series (the map dashboard). A working local-news
aggregator for Chattanooga already exists as a standalone app (`../chattnews`: RSS polling of 4
local outlets, story clustering across outlets, one-card-per-story UI), but it runs as a separate
stack with its own SQLite DB and vanilla-JS page. Absorbing it into LocalDash gives one deployment,
one database, and one dashboard — and exercises the feature-namespace architecture that was built
exactly for adding a non-geo feature beside `timeseries`.

## What Changes

- **New `news` backend feature**: port ChattNews's fetch → cluster → serve pipeline into LocalDash.
  RSS feeds fetched on an APScheduler job (replacing ChattNews's bespoke asyncio loop), articles
  stored in Postgres (new `news_sources` / `news_feeds` / `news_articles` tables via a hand-written
  Alembic migration — plain relational, no PostGIS/Timescale), title-similarity clustering ported
  as-is, stories/sources/refresh endpoints under `/api/v1/news/`. New dependency: `feedparser`.
- **New `frontend-news` feature**: `frontend/src/features/news/` Svelte port of ChattNews's
  single-page UI (category tabs, story cards with per-outlet links, sources/feed-health footer,
  refresh button) at behavioral parity. It becomes the homepage (`/`).
- **BREAKING — map moves off the homepage**: the timeseries dashboard moves from `/` to `/map`.
  Anyone bookmarking `/` for the map now lands on news.
- **Client-side routing in the frontend shell**: a tiny hand-rolled path router in
  `frontend/src/lib/` (two routes; no router dependency), a shell nav (News / Map), and an SPA
  fallback in the FastAPI static serving so deep links like `/map` return `index.html`.
- **ChattNews the standalone app is retired** once this ships; its `chattnews.db` is not migrated
  (7-day story window — a fresh fetch repopulates). Its hard-won feed knowledge (browser UA to
  avoid TownNews 429s, working TFP section feeds, per-feed error isolation) is carried into the
  ported code and comments.

## Capabilities

### New Capabilities
- `news`: backend news aggregation — source/feed registry as config, scheduled RSS fetching with
  per-feed error isolation, per-source GUID dedup, cross-outlet story clustering, story/source read
  models, and the `/api/v1/news/` API (stories, sources, refresh).
- `frontend-news`: the news feed UI at `/` — category tabs, story cards (title, summary, category,
  one link per outlet, timestamps), sources footer with feed health, manual refresh.

### Modified Capabilities
- `app-shell`: the static mount gains an SPA fallback requirement — non-`/api` paths that don't
  match a built asset serve `index.html` (so client-side routes deep-link); `/api` still always wins.
- `frontend-shell`: the shell composes features per-route instead of a single mount point — adds the
  requirement for a minimal path router in `lib/`, a shell nav, and route registration as the
  "one line to add a feature" contract; the build/serve requirement drops the words "without backend
  code changes" (the SPA fallback is a backend change owned by `app-shell`).

## Impact

- **Backend**: new `app/news/` package (config/registry, fetcher, clustering, stories read model,
  SQLAlchemy models); new router `app/api/news.py` + one `include_router` line in `main.py`; one
  new Alembic migration; scheduler gains one job (news refresh, serialized with the manual refresh
  endpoint); `pyproject.toml` gains `feedparser`.
- **Frontend**: new `frontend/src/features/news/`; `App.svelte` becomes a router shell with nav;
  `frontend/src/lib/router` added; timeseries feature untouched internally (its mount moves, and
  the connection indicator moves with it since it is timeseries-specific).
- **API surface**: `/api/v1/news/stories`, `/api/v1/news/sources`, `POST /api/v1/news/refresh`.
  No changes to `/api/v1/timeseries/*`.
- **Ops**: no new containers; news data lives in the existing Postgres. The separate chattnews
  Docker stack is decommissioned after cutover.
