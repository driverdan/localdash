## Why

The `README.md` and `AGENTS.md` describe a substantially smaller app than the one
that exists. The README still frames LocalDash as a single-feature geo dashboard
served at `/`, lists only 2 of the 4 geo sources, and documents an API surface
(flat `/api/...` paths, `/api/ws/live`) that has been fully replaced by versioned,
feature-namespaced routes (`/api/v1/<feature>/...`). `AGENTS.md` is also behind:
it describes two features and three geo sources, omitting the `tnaw` collector and
the entire Events feature. New contributors and agents reading these canonical docs
get wrong routes, a wrong feature list, and a dead API reference.

## What Changes

- **Rewrite `README.md`** to describe the current **three-feature** app:
  News (`/`), Timeseries map (`/map`), and Events (`/events`).
  - Add **News** and **Events** feature sections (what each aggregates and its
    fetch pipeline), alongside the existing timeseries description.
  - Geo sources: document all **4** collectors — `hc911`, `tdot`, `epb`, `tnaw`
    (was: only `hc911` + `tdot`).
  - **BREAKING (docs)**: Replace the entire API table with the versioned,
    feature-namespaced surface: `/api/v1/config`, `/api/v1/timeseries/*` (incl.
    `/entities`, `/entities/{id}/track`, `/observations`, `/sources`, `/ws`),
    `/api/v1/news/*`, `/api/v1/events/*`. Remove the stale flat paths
    (`/api/active`, `/api/ws/live`, etc.).
  - Fix the quick-start "open the dashboard" guidance to distinguish `/` (news
    homepage) from `/map` (the map).
  - Scope the snapshot→time-series and source-agnostic data-model sections to the
    timeseries feature, and note that News and Events have their own tables and
    pipelines outside the collector/ingest path.
- **Update `AGENTS.md`** to match reality: three features (add Events), the fourth
  geo collector (`tnaw`), and an Events architecture note (`app/events/`, sources
  carcruisefinder/ical/meetup, geocode→dedup→tag, `/api/v1/events`, `/events`).

No application code, config, or behavior changes — documentation only.

## Capabilities

### New Capabilities
- `project-documentation`: Requirements governing that the canonical project docs
  (`README.md`, `AGENTS.md`) accurately reflect the app's current features,
  geo sources, routes, and public API surface.

### Modified Capabilities
<!-- None: no existing capability's requirements change; this only adds documentation-accuracy requirements. -->

## Impact

- **Files**: `README.md` (full rewrite), `AGENTS.md` (feature/source/API sync).
- **Code / APIs / dependencies**: none — no runtime, schema, or config changes.
- **Audience**: contributors and agents onboarding via the canonical docs; the API
  reference becomes correct and usable again.
