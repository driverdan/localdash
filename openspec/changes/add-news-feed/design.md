## Context

LocalDash is FastAPI + async SQLAlchemy + Postgres (Timescale/PostGIS) with an APScheduler poll
loop and a Svelte 5 SPA organized in feature namespaces (`frontend/src/features/<feature>/` ↔
`/api/v1/<feature>/`). Today there is one feature (`timeseries`) and the SPA has no router —
`App.svelte` mounts the map dashboard directly at `/`.

ChattNews (`../chattnews`) is a working standalone aggregator: `fetch → cluster → serve`.
`fetcher.py` pulls per-section RSS feeds with feedparser (sync, run in threads), dedups per source
by GUID; `clustering.py` merges same-story articles across outlets with union-find over title
similarity (pure Python); `stories.py` builds the story read model; storage is SQLite with
config-as-code upserted at startup; the frontend is one vanilla-JS HTML page. Its CLAUDE.md
records hard-won feed knowledge (browser UA or TownNews returns 429, which TFP feeds work, feeds
erroring must never abort the cycle) that must survive the port.

This change absorbs ChattNews into LocalDash as the homepage and moves the map to `/map`.

## Goals / Non-Goals

**Goals:**
- News feature at behavioral parity with ChattNews (same pipeline, same UI capabilities).
- News as a proper sibling feature: `/api/v1/news/` + `frontend/src/features/news/`, zero changes
  inside the timeseries feature's internals.
- One storage engine: news tables live in the existing Postgres.
- Multi-page shell: `/` (news) and `/map` (timeseries) with working deep links.
- Retire the standalone chattnews deployment.

**Non-Goals:**
- No changes to the geo pipeline (collectors, ingest, entities/observations) — news does not flow
  through `NormalizedObservation`.
- No live WebSocket updates for news (ChattNews has none; 15-minute polling + manual refresh is
  the model). Can be added later.
- No migration of existing `chattnews.db` data (7-day story window; a fresh fetch repopulates).
- No article geolocation / map integration of news stories (interesting, later).
- No changes to clustering behavior or feed source list beyond the port.

## Decisions

### 1. News is a sibling feature, not a collector
The collector → ingest pipeline is geo-timeseries (geometry, active/closed lifecycle, hypertable).
Articles have none of that; forcing them into `entities`/`observations` would abuse the schema.
News gets its own package `app/news/` (registry/config, models, fetcher, clustering, stories) and
its own router `app/api/news.py`. *Alternative rejected:* a `BaseCollector` subclass — would
require faking geometry and lifecycle, and ingest's closure sweep makes no sense for articles.

### 2. Storage: Postgres tables, hand-written Alembic migration
Three tables mirroring ChattNews's schema: `news_sources`, `news_feeds`, `news_articles`
(FKs source→feed→article, `UNIQUE(source_id, guid)` dedup, indexes on `published` and
`cluster_id`). Plain relational — no PostGIS/Timescale features. `news_` prefix keeps the
namespace obvious next to the timeseries tables. Config stays the source of truth: the feed
registry lives in code (`app/news/registry.py`, a structured Python constant like ChattNews's
`config.SOURCES` — too structured for env vars) and is upserted into the DB at startup, deleting
feeds removed from config. *Alternative rejected:* carrying SQLite into the container — second
storage engine, second volume, no benefit at this scale.

### 3. Scheduling: one APScheduler job + shared asyncio lock
The news refresh (fetch all feeds, then recluster) becomes one APScheduler interval job
(default 15 min, configurable via settings), registered alongside the collector jobs. ChattNews
serializes scheduled and manual refreshes with an asyncio lock; we keep that lock in `app/news/`
so `POST /api/v1/news/refresh` and the scheduled job never interleave (APScheduler's
`max_instances=1` only covers the scheduled path). The job does not touch `sources` (timeseries
telemetry table); feed health lives on `news_feeds.last_fetch/last_status` as in ChattNews.

### 4. Fetching: keep feedparser, run in threads
feedparser is sync; ChattNews wraps it in `asyncio.to_thread`, and we keep exactly that (fetch,
parse, and clustering run in threads off the event loop). DB access does not stay sync, though:
parsed articles come back to the event loop and are upserted through the app's async SQLAlchemy
session. Carry over verbatim: the browser `USER_AGENT` (TownNews 429s unfamiliar UAs),
per-feed try/except so one dead feed never aborts the cycle, and the category-from-section-feed
mapping with "specific sections before general news" ordering. *Alternative rejected:* async
httpx fetch + `feedparser.parse(bytes)` — nicer stack fit but changes proven behavior (redirects,
encodings, conditional GET handling) during a port; can revisit later.

### 5. Clustering and stories port as-is
`clustering.py` and `textutil.py` are pure Python with no framework coupling — port nearly
verbatim (union-find over title Jaccard/containment + SequenceMatcher + distinctive-token rule,
including the same-outlet exception that prevents formulaic-headline false merges). `stories.py`
becomes the read model behind `GET /api/v1/news/stories` (same response shape: categories map +
story list). Rewriting them in SQL or changing thresholds is explicitly out of scope.

### 6. Frontend routing: hand-rolled path router in `lib/`
Two routes (`/` → news, `/map` → timeseries) don't justify a dependency. A ~30-line router in
`frontend/src/lib/router.svelte.ts`: a `$state` current-path rune, `pushState` navigation helper,
`popstate` listener. `App.svelte` becomes the route table + a small nav header (News | Map).
The timeseries connection indicator ("live / disconnected") is timeseries-specific and moves out
of the shell header into the map page composition (still driven by the feature's exported
`connectionState()` — the shell may render it only on the map route, keeping import rules intact).
*Alternatives rejected:* svelte-spa-router / svelte-routing (dependency for two routes),
hash routing (`/#/map` — ugly URLs, and the SPA fallback server-side is a small change we want
anyway).

### 7. SPA fallback in the static mount
`StaticFiles(html=True)` serves `index.html` only at `/`; deep-linking `/map` would 404. Extend
the existing `NoCacheStaticFiles` subclass: on a 404 for a non-`/api` path with no file extension,
serve `index.html` instead. `/api` routes are registered before the mount, so the API always wins
unchanged. This is the one backend change owned by the shell (`app-shell` spec delta).

### 8. Frontend feature layout mirrors timeseries
`frontend/src/features/news/`: `api.ts` (typed client for `/api/v1/news/*`), `types.ts`,
`state.svelte.ts` (runes store: stories, categories, active tab, hours window, sources health),
`components/` (`NewsFeed.svelte` top-level, `CategoryTabs`, `StoryCard`, `SourcesFooter`),
`index.ts` public surface. Import rules unchanged: news imports only itself + `lib/`.

## Risks / Trade-offs

- [Feed sites block or throttle the new deployment] → carry the exact browser UA string; per-feed
  error isolation records failures in `news_feeds.last_status`, surfaced in the UI footer, so a
  broken feed is visible instead of silent.
- [Bookmarks to `/` now land on news, not the map] → accepted per proposal (BREAKING); the nav
  makes the map one click away. No redirect shim.
- [Sync feedparser in threads under the async app] → same pattern ChattNews runs today; the fetch
  is 15-minutely and bounded (~13 feeds). If it grows, switch to httpx + `feedparser.parse(bytes)`.
- [SPA fallback could mask genuinely missing assets] → fallback applies only to extension-less
  paths; asset requests (`.js`, `.css`, …) still 404 loudly.
- [Clustering quality drift Postgres vs SQLite] → clustering runs in Python on rows, not in SQL;
  the DB swap doesn't touch the algorithm. Dedup semantics (`UNIQUE(source_id, guid)` upsert that
  only upgrades category `news` → specific) must be replicated exactly in the Postgres upsert.
- [Startup ordering: registry upsert needs tables] → registry sync runs in the lifespan after
  migrations have been applied (compose already runs `alembic upgrade head` before serving; local
  dev docs already require it).

## Migration Plan

1. Ship LocalDash with the news feature; verify feeds populate and stories cluster.
2. Cut over: stop the standalone chattnews compose stack; its volume/db is abandoned (no data
   migration by design).
3. Rollback: revert the LocalDash deploy; restart the chattnews stack. News tables are additive —
   a rollback leaves them inert; the migration has a normal `downgrade()` dropping them.

## Open Questions

- None blocking. Deferred ideas recorded as non-goals (news WebSocket updates, geolocating
  stories onto the map).
