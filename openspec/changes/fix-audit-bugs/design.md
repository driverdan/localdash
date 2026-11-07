## Context

The 2026-11-06 audit compared every spec and doc against the code. Most drift was documentation;
this change covers the subset where the **code** is wrong. The fixes are independent and each is
small, but they span the backend (ingest, scheduler, weather, news, static mount), the frontend
(detail panel), and ops config (Compose, packaging, pre-commit). This document records the few
places where there was a real choice to make.

## Goals / Non-Goals

**Goals:**
- Make the code meet what the specs and docs already promise, with a regression test for each
  backend fix.
- Keep each fix local. No new dependencies, no migrations.

**Non-Goals:**
- The doc/spec-only drift from the audit (AGENTS.md architecture notes, README counts, stale
  frontend scenarios). It goes in a separate docs sync.
- Judgment-call items the audit flagged but that need a product decision:
  - news upsert refreshing title, summary and image;
  - `/sources` `enabled` reconciliation;
  - the home weather widget when weather is disabled;
  - an empty-payload guard on the closure sweep.

## Decisions

### Shared entity-feature property builder
Add `entity_properties(raw, *, id, source, external_id, category, label, last_seen_at, active,
status)` to `app/geojson.py`. It returns `{**raw, <authoritative keys>}`, so the authoritative keys
always win. Both `GET /entities` and `ingest._entity_feature` call it and then wrap the result with
`feature_geom`/`feature` as they do today.
- `last_seen_at` is serialized as ISO-8601 in both paths. The diff uses the cycle's `now`, which is
  exactly what the entity row stores.
- `status` stays a caller argument. REST derives it as `"Closed"` when the entity is inactive,
  otherwise the stored status; a diff entity is always active, so it passes `obs.status`.
- *Alternative considered:* just reorder the dict in `_entity_feature`. That would fix today's bug
  but leave two hand-maintained copies of the contract, which is how they drifted in the first
  place.

### Per-source asyncio lock in `run_collector`
A module-level `dict[str, asyncio.Lock]` keyed by `source_key`, created lazily. It wraps the whole
cycle, including telemetry recording, so `last_*` reflects the runs in the order they happened.
This matches the module-lock pattern news and events already use. A queued manual refresh then
runs a full cycle after the scheduled one, which is cheap and gives the caller fresh data.
- *Alternative considered:* reject a concurrent manual refresh with 409. The UI has no handling
  for that, and the news/events precedent is to wait.

### Weather: `get_current(force=False)`
The scheduled job calls `get_current(force=True)`, which skips only the TTL short-circuit. Locking,
stale-on-failure and AQI carry-forward run unchanged. Request handlers keep the default.
- *Alternative considered:* move `_fetched_at` to the start of the fetch, or subtract a margin.
  Both still couple the job's cadence to the cache's timing. An explicit force flag says what the
  job means.

### News: delete sources missing from the registry
`sync_registry` ends with `DELETE FROM news_sources WHERE slug NOT IN (<registry slugs>)`.
Migration 0002 already declares `ON DELETE CASCADE` on `news_feeds.source_id` and
`news_articles.source_id`, so feeds and articles go with it.
- *Alternative considered:* set `enabled=false` and keep the history. The spec's model is "the
  registry is the source of truth" and removed feeds are already deleted. Deleting removed sources
  is consistent, and a re-added source re-fetches fresh articles anyway.

### Compose: optional `env_file`, no required tunnel token
- The `app` service gets `env_file: [{path: .env, required: false}]`. This needs Compose ≥ 2.24,
  and the repo already assumes a modern Compose (profiles, `depends_on` conditions).
- `environment:` keeps only `DATABASE_URL`, which takes precedence over `env_file`, so the
  localhost URL in a copied `.env.example` cannot break the in-network DB host.
- The `SITE_NAME`, `AIRNOW_API_KEY` and `EVENTS_BLOCKED_TAGS` passthroughs are removed. `env_file`
  delivers them when set, and when unset the app's own defaults apply. That fixes the
  `EVENTS_BLOCKED_TAGS` empty-override bug.
- The tunnel token becomes `${CLOUDFLARE_TUNNEL_TOKEN:-}`. Compose interpolates every service even
  when its profile is inactive, so a `:?` guard breaks plain `docker compose up`. If someone opts
  into the tunnel profile without a token, `cloudflared` fails at start with its own error.

### Remove `RETENTION_DAYS` rather than implement it
Implementing it properly means a Timescale retention policy that reconciles with the setting at
startup: add, change, or remove the policy on `observations`, plus the question of what happens to
`entities` whose history is dropped. No one has asked for that. The setting is removed from
`Settings`, `.env.example`, README and AGENTS.md. `extra="ignore"` keeps stale `.env` files
loading.

### Small fixes
- `limit: int = Query(5000, ge=1, le=50000)`.
- SPA fallback guard: `path == "api" or path.startswith("api/")`.
- Add `"app.weather"` to `[tool.setuptools] packages`.
- Bump the pre-commit ruff rev to the version locked in `uv.lock`.
- Detail panel: add a `.catch` that sets an `error` state, but only if the entity is still the one
  open. The template shows the error in place of "Loading…".

## Risks / Trade-offs

- **Older Docker Compose.** Compose older than 2.24 rejects the long `env_file` syntax. This
  mainly affects old Debian/Ubuntu distro packages. → The README already points to the Docker
  install; Compose v2.24 dates from January 2024.
- **`.env` now reaches the container.** Placeholder values in a copied `.env.example` now take
  effect under Docker. → Every value in `.env.example` is a working default; the `USER_AGENT`
  placeholder URL is tidied up in the same edit.
- **Queued refreshes.** A manual refresh that queues behind a slow scheduled cycle makes the HTTP
  call wait longer. → The wait is bounded by one collector cycle, which already has HTTP timeouts.
- **Deleting a news source loses its stored articles.** → That is the intended registry
  semantics, and articles age out of the 7-day story window anyway.
