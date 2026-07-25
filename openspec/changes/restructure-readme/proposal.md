## Why

The `README.md` has drifted badly from the app that ships and serves three
audiences at once. It advertises "three sibling features" when four ship, claims
News is at `/` when `/` is now the Home digest page and News moved to `/news`,
never mentions the Weather feature at all, and names an `X-Frontend-Auth` setting
that no longer exists in `app/config.py`. Structurally, ~60% of its 283 lines are
contributor material (data model, endpoint tables, "adding a collector") and ~12
lines are agent process copied from `AGENTS.md` — so a newcomer wanting "what is
this and how do I run it" walks 95 lines of hypertable schema before reaching
`docker compose up --build`. Because that contributor material is duplicated in
`AGENTS.md`, one copy is always stale, and it is already the README's copy that
rotted.

## What Changes

- **Rewrite `README.md` for one audience — someone new to the project.** Target
  roughly 100 lines: what LocalDash is, the features and their routes, quick
  start, configuration pointers, public exposure, contributing links, license.
- **Correct every factual drift**, listed in `design.md`: four features not
  three; Home at `/`; News at `/news`; the Weather feature (NWS + AirNow, no DB
  tables, no scheduler job — explicitly *not* a collector); the `chattzoo` events
  source; the eight registered news outlets; the configurable `SITE_NAME`; the
  theme switcher; and removal of the ghost `X-Frontend-Auth` reference.
- **Keep a short summary of the snapshot → time-series idea** (~4 lines) as the
  hook that explains why this is not four RSS readers, and drop the hypertable /
  PostGIS / JSONB detail, which `AGENTS.md` already covers.
- **Replace the four hand-maintained API endpoint tables** (39 lines, already
  missing `/api/v1/weather/current`) with a pointer to the auto-generated Swagger
  UI at `/docs`, which `app/main.py` already serves.
- **Add `CONTRIBUTING.md`** and move the human contributor material there: the
  local-venv quick start, tests, and pre-commit linting. The README links to it.
- **Remove the "Git workflow" and "Adding a geo data source" sections** from the
  README; both are agent process already specified in `AGENTS.md`, which
  `CONTRIBUTING.md` links to.
- **Add a screenshot** of the dashboard at the top of the README.
- **State that LocalDash targets Chattanooga today with multi-city support
  planned**, so the intro answers "can I use this for my city?" honestly.
- **Modernize the stale `project-documentation` spec**, which currently asserts
  News at `/`, three features, and a `/api/v1/timeseries/ws` endpoint that
  `app/main.py:81` documents as removed.

## Capabilities

### New Capabilities

- `contributor-documentation`: `CONTRIBUTING.md` as the home for human
  contributor setup — local development environment, running tests, and the
  linting/formatting hooks — and its obligation to stay accurate.

### Modified Capabilities

- `project-documentation`: the README's audience and scope change from
  "everything" to "newcomer orientation". The requirement that the README carry a
  full API reference is removed in favour of pointing at the served OpenAPI docs;
  the feature/route requirement is corrected to the four shipped features and
  their current routes; the geo-source requirement gains the rule that
  non-collector features are not listed as sources; and the `AGENTS.md`
  requirement is corrected from three features to four.
- `code-quality-tooling`: the "Developer setup contract" requirement names
  `README.md` as a place that must instruct contributors to run `pre-commit
  install`. Since that material moves to `CONTRIBUTING.md`, the requirement is
  retargeted to `AGENTS.md` and `CONTRIBUTING.md`, with the README obliged to
  link there. *(Found during implementation, not in the original proposal.)*

## Impact

- **Docs only — no application code changes.** `README.md` (rewritten),
  `CONTRIBUTING.md` (new), `openspec/specs/project-documentation/spec.md`
  (modernized via the delta).
- One new committed image asset for the screenshot.
- `AGENTS.md` is corrected only where the delta spec requires it (feature count);
  it is otherwise already accurate and is not restructured by this change.
- No API, database, or dependency impact. Nothing in `app/` or `frontend/` is
  touched, so CI's changed-path filtering should skip the code jobs.
