## 1. Live diff property contract

- [ ] 1.1 Add `entity_properties(raw, *, id, source, external_id, category, label, last_seen_at, active, status)` to `app/geojson.py` (raw first, authoritative keys override; `last_seen_at` ISO-8601)
- [ ] 1.2 Use it in `GET /entities` (`app/api/timeseries.py`) with no change to the REST output
- [ ] 1.3 Use it in `ingest._entity_feature` (`last_seen_at=now`, `active=True`, `status=obs.status`)
- [ ] 1.4 Test: a diff feature from an observation whose raw properties carry `id` keeps the entity id and includes `last_seen_at`/`active`; a unit test of `entity_properties` override order

## 2. Serialized collector runs

- [ ] 2.1 Add a lazily created per-`source_key` `asyncio.Lock` in `app/scheduler.py` and wrap the whole `run_collector` cycle (including `_record_run`)
- [ ] 2.2 Test: two concurrent `run_collector` calls for one source never overlap inside `collect`/`ingest`, while different sources run concurrently (fake collector, patched ingest/record)

## 3. Weather job forces refresh

- [ ] 3.1 Add `force: bool = False` to `WeatherService.get_current`, skipping only the TTL short-circuit
- [ ] 3.2 Have `run_weather_refresh` call `get_current(force=True)`
- [ ] 3.3 Test: `force=True` within the TTL hits upstream; the default within the TTL still hits the cache

## 4. News registry removes dropped sources

- [ ] 4.1 In `sync_registry`, delete `news_sources` rows whose slug is not in `SOURCES` (feeds/articles cascade)
- [ ] 4.2 DB test: a stored source absent from the registry is deleted with its feeds and articles; registry sources remain

## 5. Small backend fixes

- [ ] 5.1 `/observations` `limit`: `Query(5000, ge=1, le=50000)`, plus a test that `limit=0` and `limit=-1` return 422
- [ ] 5.2 SPA fallback: treat `path == "api"` like `api/`, plus a test that `GET /api` and `GET /api/` return 404
- [ ] 5.3 Add `app.weather` to `[tool.setuptools] packages` in `pyproject.toml` (re-lock if uv requires it)

## 6. Remove RETENTION_DAYS

- [ ] 6.1 Remove `retention_days` from `app/config.py`
- [ ] 6.2 Remove `RETENTION_DAYS` from `.env.example`, `README.md` and the AGENTS.md config list

## 7. Docker Compose

- [ ] 7.1 Change the tunnel token to `${CLOUDFLARE_TUNNEL_TOKEN:-}`
- [ ] 7.2 Add `env_file: [{path: .env, required: false}]` to `app`; keep only `DATABASE_URL` in `environment`; drop the `SITE_NAME`/`AIRNOW_API_KEY`/`EVENTS_BLOCKED_TAGS` passthroughs and update the comments
- [ ] 7.3 Tidy `.env.example`: the `USER_AGENT` placeholder URL becomes the real default; add `EVENTS_BLOCKED_TAGS=topics`
- [ ] 7.4 Verify `docker compose config` succeeds with no `.env` and with a copy of `.env.example`, then `docker compose up --build` and confirm the app serves and the `topics` blocklist is effective

## 8. Frontend detail panel

- [ ] 8.1 In `DetailPanel.svelte`, add a `.catch` that sets an error state (ignored if another entity is open now) and render an error message in place of "Loading…"
- [ ] 8.2 `npm run check` and `npm run build` pass

## 9. Tooling and verification

- [ ] 9.1 Bump the `.pre-commit-config.yaml` ruff rev to the `uv.lock` version (v0.17.2), then run `pre-commit run --all-files` and commit any resulting formatting
- [ ] 9.2 Full `pytest` passes against the Dockerized DB
