## Why

The 2026-11-06 code-vs-spec audit found that, apart from the bugs fixed in `fix-audit-bugs`,
the rest of the drift is in the text. Specs describe behavior that has since changed, and
AGENTS.md, README, `.env.example`, one API doc and several code comments describe an older app.
Agents onboard from AGENTS.md and the specs, so stale claims there lead directly to wrong code.
In every case below **the code is correct**, and the text is brought in line with it.

## What Changes

- **Spec corrections.** Each one describes shipped behavior; no code changes.
  - `events`:
    - Five default sources are registered, not three, and the Chattanooga Zoo is one of them.
    - The ingest radius filter also applies to coordinates the source supplies.
    - CitySpark's tag vocabulary comes from the `PortalScripts` bootstrap request, and paging
      is capped.
    - Zoo event titles prefer the detail page's heading.
  - `news`:
    - Majority match only rejects a single hit for stories of three or more articles.
    - With `hours=N`, story aggregates cover only the articles inside the window.
  - `timeseries`: documents the closure sweep that already happens:
    - closing an entity sets `last_seen_at` and writes a `Closed` observation with its reason;
    - an empty payload closes every active entity of that source;
    - each collector runs once at startup;
    - `last_error` is redacted.
  - `frontend-shell`:
    - The dev proxy path is `/api/v1/ws`.
    - The connection indicator shows on every route.
    - Cross-feature imports are allowed only through `index.ts`.
    - Wiring a feature in also needs a nav link, a stylesheet import and live registration.
  - `frontend-home`: `index.ts` also exports `registerHomeLive`.
  - `frontend-debug`:
    - The example routes with a registered action are `/news` and `/events`.
    - The "on every route" scenario lists all four routes.
    - On mobile the π button is fixed at bottom-center.
  - `frontend-news`:
    - The debug action runs on `/news`, not `/`, and is unregistered when the user leaves
      `/news`.
    - The sources footer's article count is per outlet.
  - `frontend-events`: removes the "automatic 5-minute reload" reference; reloads come from live
    updates.
  - `frontend-timeseries`:
    - Removes the migration-era "Behavioral parity with the replaced UI" requirement.
    - Completes the category-to-icon table with `tnaw` and the `map-pin` fallback.
    - Describes the status-label lookup as it works: a lookup across sources, with raw codes
      assumed unique.
  - `project-documentation`: AGENTS.md describes Weather as having no DB tables but a scheduled
    refresh job.
- **Purpose prose, edited by hand at archive.** `weather` drops "no scheduler job" and `events`
  adds the Chattanooga Zoo.
- **Docs.**
  - AGENTS.md:
    - routes and the feature list, including home;
    - the news categorization, fetch and clustering descriptions;
    - weather and its scheduler job, plus the full job list;
    - the CI description;
    - the dependency-pinning policy;
    - geometry (any geometry plus fingerprint);
    - the API conventions (weather namespace, `/api/v1/ws`);
    - the config list (events, AirNow);
    - the DB-backed test list.
  - README: nine outlets; events sorted by start time; no map time-scrubber claim.
  - `.env.example`:
    - adds a News section;
    - adds the events tribe and CitySpark settings, with an accurate events comment;
    - notes that `CENTER_*` also sets the weather location.
  - `docs/tdot-smartway-api.md`: rewrites the LocalDash mapping section to describe the single
    merged `tdot` collector that ships; `docs/hc911-api.md` points to AGENTS.md.
- **Comments and housekeeping.**
  - Stale comments in `app/config.py`, `app/main.py`, `frontend/src/lib/router.svelte.ts` and
    `frontend/src/styles/base.css`.
  - The root `.prettierignore` moves to `frontend/`, where prettier actually reads it.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `events`: default source set, radius filter on supplied coordinates, CitySpark bootstrap
  request, zoo title source.
- `news`: majority-match wording, in-window story aggregates.
- `timeseries`: adds a requirement documenting the closure sweep and run telemetry.
- `frontend-shell`: dev proxy path, cross-feature import rule, feature wiring steps, the
  indicator on every route.
- `frontend-home`: the `index.ts` surface includes live registration.
- `frontend-debug`: example routes, mobile button position.
- `frontend-news`: the debug action's route and scope, per-outlet footer counts.
- `frontend-events`: removes the 5-minute reload reference.
- `frontend-timeseries`: removes the parity requirement, completes the icon table, corrects the
  status-label lookup.
- `project-documentation`: the AGENTS.md weather scenario.

## Impact

- **Text only.** Specs, Markdown docs, `.env.example` and code comments change. There are no
  behavior changes, migrations or new dependencies.
- **Files:** `AGENTS.md`, `README.md`, `.env.example`, `docs/tdot-smartway-api.md`,
  `docs/hc911-api.md`, comment lines in `app/config.py`, `app/main.py`,
  `frontend/src/lib/router.svelte.ts` and `frontend/src/styles/base.css`, and `.prettierignore`,
  which moves to `frontend/.prettierignore`.
- **Out of scope:** the audit's judgment-call code items:
  - the news upsert refreshing title, summary and image;
  - reconciling `/sources` `enabled` with the registered collectors;
  - a guard for empty payloads on the closure sweep;
  - the home weather widget when weather is disabled;
  - collapsing the news sources footer to one row per outlet.
