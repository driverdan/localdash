## Why

A code-vs-spec audit (2026-11-06) found a batch of real bugs where the shipped code
does not do what the specs and docs promise. Some are user-visible: the documented Docker
quick start fails on a fresh clone, live map updates sort new entities last, and the weather
strip refreshes at half the documented rate. Others are latent: concurrent ingests can collide,
a removed news outlet keeps being fetched, and one documented setting does nothing. Each fix is
small, and fixing them together closes out the audit's code findings in one reviewable change.

## What Changes

- **Docker quick start works on a fresh clone.** The `cloudflared` tunnel token stops being a
  hard-required interpolation, so `docker compose up --build` no longer fails when the opt-in
  `tunnel` profile is unused.
- **Docker honors `.env`.** The app service loads an optional `.env` (`env_file`, not required),
  so the settings README tells users to set (center, tile layer, source toggles, …) take effect
  under Docker. The per-variable passthroughs it replaces go away. That includes
  `EVENTS_BLOCKED_TAGS: ${EVENTS_BLOCKED_TAGS:-}`, which silently overrode the `topics` default
  with an empty blocklist.
- **Live diff features match REST entity features.** Diff `new`/`updated` features carry the same
  property contract as `GET /entities`: raw source properties first, then the authoritative keys
  (`id`, `source`, `external_id`, `category`, `label`, `last_seen_at`, `active`, `status`). One
  shared helper builds both.
- **Timeseries runs are serialized per source.** A manual refresh that arrives during a scheduled
  tick waits for it instead of running a second concurrent `ingest()` on the same source.
- **The weather job refreshes every tick.** The scheduled job bypasses the TTL check, so the
  proactive refresh happens every `weather_cache_minutes` rather than every other interval.
- **News registry sync removes dropped outlets.** A source whose slug is no longer in the
  registry is deleted at startup, along with its feeds and articles, so it stops being fetched
  and listed.
- **BREAKING (config): remove `RETENTION_DAYS`.** It was documented but never read. It is removed
  from settings, `.env.example`, README and AGENTS.md instead of half-implementing a Timescale
  retention policy. An existing `.env` that sets it is harmless (unknown keys are ignored).
- **Input and edge-case fixes.**
  - `/observations` rejects `limit < 1` with a 422 instead of a 500.
  - A bare `/api` or `/api/` never falls back to `index.html`.
  - `app.weather` is added to the packaged modules.
  - The map detail panel shows an error instead of "Loading…" forever when its fetch fails.
- **Tooling.** The pre-commit ruff hook rev is bumped to match the locked ruff version, so the
  hook and `uv run ruff` format identically.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `live-updates`: diff features share the REST entity property contract. Scheduled and manual
  timeseries runs for one source are serialized.
- `timeseries`: the observations `limit` must be ≥ 1. Manual refresh is serialized with the
  scheduled tick and returns the run result (`source`, `status`, `error`, `count`).
- `weather`: each scheduled job tick forces an upstream refresh regardless of cache age.
- `news`: registry sync also deletes sources removed from the registry.
- `events`: the blocklist default is `topics`, which the spec previously recorded as empty.
- `app-shell`: the bare `/api` path is explicitly excluded from the SPA fallback.
- `frontend-timeseries`: the detail panel shows an error state when its fetch fails.

## Impact

- **Code:**
  - Backend: `app/ingest.py`, `app/api/timeseries.py`, `app/geojson.py` (shared feature helper),
    `app/scheduler.py`, `app/weather/service.py`, `app/news/registry.py`, `app/main.py`,
    `app/config.py`.
  - Frontend: `frontend/src/features/timeseries/components/DetailPanel.svelte`.
- **Config and ops:** `docker-compose.yml`, `.env.example`, `pyproject.toml` (packages list),
  `.pre-commit-config.yaml`.
- **Docs:** README and AGENTS.md lines that mention `RETENTION_DAYS` or the Docker env behavior.
- **Tests:** new or updated tests for diff/REST property parity, collector-run serialization, the
  forced weather refresh, news source removal, the observations `limit` lower bound, and the bare
  `/api` fallback.
- **No DB migration.** News deletion relies on the existing `ON DELETE CASCADE`.
- **Out of scope:** doc- and spec-only drift from the audit (AGENTS.md architecture, README
  counts, stale spec scenarios). That lands in a separate sync PR.
