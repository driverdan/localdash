## Context

`README.md` and `AGENTS.md` are the two canonical entry-point docs. Both drifted
behind the code as features and sources were added:

- The app grew from one geo feature to **three** user-facing features — News (`/`),
  Timeseries map (`/map`), Events (`/events`) — with the map moving off `/`.
- Geo collectors grew from 2 to **4** (`hc911`, `tdot`, `epb`, `tnaw`).
- The API was restructured from flat `/api/...` paths to **versioned,
  feature-namespaced** routes (`/api/v1/<feature>/...`), including moving the
  WebSocket to `/api/v1/timeseries/ws`.

The README still reflects the pre-restructure world; `AGENTS.md` reflects an
intermediate state (two features, three sources). This is a documentation-only
change: no runtime, schema, config, or behavior changes.

## Goals / Non-Goals

**Goals:**
- Make `README.md` a faithful description of the shipped app: features, routes,
  all four geo sources, and the current versioned API surface.
- Bring `AGENTS.md` current: three features (add Events) and the `tnaw` collector.
- Ground every documented fact in the code so the docs match `app/collectors/`,
  `app/main.py` routing, `app/api/*.py`, and `frontend/src/App.svelte` routes.

**Non-Goals:**
- No changes to application code, config, schema, dependencies, or behavior.
- No exhaustive per-parameter API docs beyond what already exists in the README's
  table style — parity of accuracy, not expanded reference depth.
- No restructuring of `AGENTS.md` beyond the feature/source/API corrections needed
  for accuracy.

## Decisions

**Source of truth = the code, not AGENTS.md.** `AGENTS.md` itself lags reality
(missing `tnaw` and the Events feature), so both docs are reconciled against the
code (`build_collectors()`, `include_router` calls in `main.py`, the `@router`
decorators in `app/api/*.py`, and the route table in `App.svelte`). Alternative
considered: sync README to AGENTS.md — rejected because AGENTS.md is itself stale.

**Full README rewrite over surgical patches.** The framing (single geo dashboard at
`/`) is wrong at the structural level — opening summary, "how it works" diagram,
quick-start route, and API table all assume it. A rewrite is cleaner than many
interleaved edits and avoids leaving contradictory framing. The accurate
snapshot→time-series and data-model sections are preserved, re-scoped as the
*timeseries* feature.

**Capability captures documentation-accuracy requirements.** The new
`project-documentation` capability encodes what the canonical docs must always
reflect (features+routes, all collectors, current API surface), so future feature
changes have a spec-level reason to touch the docs.

## Risks / Trade-offs

- **[Docs re-drift as the app evolves]** → The `project-documentation` spec makes
  doc updates a stated requirement when features/sources/routes change; reviewers
  can point to it. Not enforced by CI (out of scope).
- **[Rewrite drops a still-accurate README detail]** → Preserve the correct
  sections verbatim where possible (data model, snapshot→time-series, Cloudflare
  tunnel, tests, pre-commit, license); only reframe and correct what is wrong.
- **[Documented routes silently diverge from code]** → Cross-check the final API
  table against the `@router` decorators and `main.py` prefixes before finishing.

## Migration Plan

Not applicable — documentation-only change, no deploy or rollback steps. Reverting
is a straight `git revert` of the docs commit.

## Open Questions

None outstanding — scope, target docs, and depth were confirmed before proposing.
