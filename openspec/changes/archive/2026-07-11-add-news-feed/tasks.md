## 1. Backend: storage and registry

- [x] 1.1 Add `feedparser` to `pyproject.toml` dependencies and install into the venv
- [x] 1.2 Create `app/news/models.py`: SQLAlchemy models `NewsSource`, `NewsFeed`, `NewsArticle`
      (shared `Base`; FKs, `UNIQUE(source_id, guid)`, indexes on `published` and `cluster_id`)
- [x] 1.3 Write Alembic migration `0002` (hand-written SQL, with `downgrade()`) creating
      `news_sources`, `news_feeds`, `news_articles`
- [x] 1.4 Create `app/news/registry.py`: port ChattNews `config.SOURCES` + `CATEGORIES` verbatim
      (4 outlets, section→category mapping, specific-before-general feed order, browser
      `USER_AGENT` constant, story-window and refresh-interval knobs wired to `config.py` settings)
- [x] 1.5 Create registry→DB sync (async port of ChattNews `init_db()` upsert/delete semantics),
      called from the app lifespan; verify removed feeds get deleted

## 2. Backend: fetch, cluster, serve

- [x] 2.1 Port `textutil.py` and `clustering.py` into `app/news/` (pure-Python, near-verbatim;
      clustering reads/writes articles via the async session, similarity logic unchanged including
      the cross-outlet-only distinctive-token rule)
- [x] 2.2 Create `app/news/fetcher.py`: feedparser in `asyncio.to_thread`, per-feed error isolation
      writing `last_fetch`/`last_status`, HTML-stripped summaries, async upsert with
      category-upgrade-only dedup on `(source_id, guid)`
- [x] 2.3 Create `app/news/refresh.py` (or equivalent): `refresh()` = fetch all + recluster,
      serialized by a module-level `asyncio.Lock`, returning per-source results + cluster count
- [x] 2.4 Create `app/news/stories.py`: port the story read model (headline from earliest, wordiest
      summary sentence-truncated, majority-vote category with specific-beats-news ties, one link per
      outlet, sorted by latest activity) and the sources/feed-health query
- [x] 2.5 Create `app/api/news.py` router: `GET /stories?hours=`, `GET /sources`, `POST /refresh`;
      add `include_router(news.router, prefix="/api/v1/news")` in `main.py`
- [x] 2.6 Register the news refresh job in `build_scheduler()` (interval from settings, default
      15 min, immediate first run, `max_instances=1`)

## 3. Backend: tests

- [x] 3.1 Pure tests: clustering merge/no-merge cases (cross-outlet merge, same-outlet formulaic
      headlines stay separate), story read-model aggregation (counts, category vote, one link per
      outlet), summary truncation
- [x] 3.2 DB-backed tests (auto-skip pattern from `conftest.py`): registry sync
      upsert/delete, article upsert dedup + category upgrade, stories/sources API round-trip via
      the app

## 4. Frontend: shell routing

- [x] 4.1 Create `frontend/src/lib/router.svelte.ts`: reactive current path, `navigate()` via
      `pushState`, `popstate` listener
- [x] 4.2 Rework `App.svelte`: nav header (News | Map), route table `/` → news, `/map` →
      timeseries; move the connection indicator so it renders only on the map route
- [x] 4.3 Extend `NoCacheStaticFiles` in `main.py` with the SPA fallback (extension-less non-`/api`
      404s serve `index.html`; asset 404s stay 404)

## 5. Frontend: news feature

- [x] 5.1 Create `frontend/src/features/news/` skeleton: `types.ts`, `api.ts` (stories/sources/
      refresh clients), `state.svelte.ts` (stories, categories, active tab, hours window,
      multi-source-only, sources, status text; 5-minute auto-reload), `index.ts`
- [x] 5.2 Components: `NewsFeed.svelte` (toolbar: window select, multi-source toggle, refresh
      button + status), `CategoryTabs.svelte` (All + present categories), `StoryCard.svelte`
      (badges, time-ago, headline link, summary, outlet pills), `SourcesFooter.svelte`
      (feed-health table); grouped-by-category All view; empty/error states
- [x] 5.3 Port ChattNews visual styling into the components (category badge, multi-source badge,
      pill links) consistent with the existing app shell styles

## 6. Verify and cut over

- [x] 6.1 `npm run check` passes with 0 errors; `pytest` passes (DB tests against
      `docker compose up -d db`)
- [x] 6.2 End-to-end: `docker compose up --build`, confirm migrations apply, feeds fetch (check
      `/api/v1/news/sources` statuses), stories cluster, homepage shows the feed, `/map` deep-link
      reloads correctly, nav + back button work, timeseries dashboard unchanged at `/map`
- [x] 6.3 Update `CLAUDE.md` (news feature, routes, new tables, feedparser, feed gotchas carried
      from ChattNews) and `README`/docs if present
- [x] 6.4 Decommission note: stop the standalone chattnews compose stack (manual, outside this
      repo); record in the PR description
