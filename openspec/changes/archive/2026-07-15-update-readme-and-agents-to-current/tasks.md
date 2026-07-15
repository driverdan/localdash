## 1. Verify ground truth from the code

- [x] 1.1 Confirm the geo collectors from `app/collectors/__init__.py` `build_collectors()` and each class's `source_key` / `name` (`hc911`, `tdot`, `epb`, `tnaw`)
- [x] 1.2 Confirm the API surface: `include_router` prefixes in `app/main.py` and the `@router` decorators in `app/api/{root,timeseries,news,events}.py` (paths, methods, key query params)
- [x] 1.3 Confirm the frontend routes from `frontend/src/App.svelte` (`/` news, `/map` timeseries, `/events` events)

## 2. Rewrite README.md

- [x] 2.1 Rewrite the opening summary + "how it works" to frame LocalDash as a three-feature dashboard (News `/`, Map `/map`, Events `/events`)
- [x] 2.2 Add a News feature section (RSS aggregation, cross-outlet clustering, its own tables/pipeline outside collector/ingest)
- [x] 2.3 Add an Events feature section (car cruises / civic meetings / Meetup / iCal, geocode→dedup→tag pipeline)
- [x] 2.4 Update the built-in geo sources list to all four collectors (`hc911`, `tdot`, `epb`, `tnaw`), linking the `docs/` API references
- [x] 2.5 Replace the API table with the versioned, feature-namespaced routes (`/api/v1/config`, `/api/v1/timeseries/*` incl. `/entities`, `/entities/{id}/track`, `/observations`, `/sources`, `/sources/{key}/refresh`, `/ws`; `/api/v1/news/*`; `/api/v1/events/*`); remove all stale flat paths
- [x] 2.6 Fix the quick-start "open the dashboard" guidance to distinguish `/` (news) from `/map` (map)
- [x] 2.7 Re-scope the snapshot→time-series and source-agnostic data-model sections as the timeseries feature; preserve still-accurate sections (Cloudflare tunnel, tests, pre-commit, license)

## 3. Update AGENTS.md

- [x] 3.1 Change the "two features" framing to three (add Events) in the "What this is" section
- [x] 3.2 Add `tnaw` (TN American Water Advisories) to the geo-source list
- [x] 3.3 Add an Events feature architecture note (`app/events/`, sources carcruisefinder/ical/meetup, geocode→dedup→tag, `/api/v1/events` namespace, `/events` route)

## 4. Verify

- [x] 4.1 Cross-check the final README API table against `main.py` prefixes and the `@router` decorators — no path documented that isn't served, none served-and-user-facing left undocumented
- [x] 4.2 Grep README + AGENTS.md for stale references (`/api/active`, `/api/ws/live`, "two features", 2-source lists) and confirm none remain
- [x] 4.3 Run `openspec validate --change "update-readme-and-agents-to-current"` and confirm it passes
