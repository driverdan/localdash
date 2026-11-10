## Why

The backend has been kept split by feature even though no written rule asks for it. `app/news`,
`app/events`, `app/weather` and `app/collectors` never import from each other today. The split
comes from how AGENTS.md reads: news, events and weather are called "sibling features" that "do
not flow through collectors/ingest", and the frontend section calls its strict import rules the
mirror of "the API's feature-namespace convention". Together these read like a backend
code-separation mandate. That reading has produced duplicate code, for example:

- the same browser User-Agent string in `app/news/registry.py` and
  `app/events/sources/carcruisefinder.py`, whose docstring cites the news one as precedent instead
  of importing it;
- EWKT point builders in both `app/ingest.py` and `app/events/ingest.py`;
- the same keyword-matching mechanism in `app/news/classify.py` and `app/events/tagging.py`.

The owner has decided that the backend is one application, with no mandated separation between its
feature packages. This change writes that decision down so contributors and agents follow it, and
it lands before the refactoring changes that rely on it.

## What Changes

- **AGENTS.md: new "Backend code organisation" guideline.** Packages under `app/` organise code;
  they are not boundaries. Any backend module may import from any other. Reusing or promoting
  existing code is preferred over writing a second copy. The guideline also gives short, practical
  advice on avoiding import cycles, and says plainly that it adds no new boundary rule.
- **AGENTS.md: reword passages that read as a backend mandate.** The data-flow facts stay
  ("sibling feature", "does not flow through collectors/ingest"), and the text says they describe
  data flow, not import rules. The frontend paragraph's "mirrors the API's feature-namespace
  convention" lead-in is reworded so it no longer implies the backend has matching import rules.
  The frontend import rules themselves do not change.
- **What stays, stated explicitly:** `/api/v1/<feature>/` URL namespacing, one router module per
  feature in `app/api/`, every frontend rule, and the data-flow facts.
- **`project-documentation` spec:** a new requirement that AGENTS.md carries this guideline and
  separates the data-flow facts from code organisation.
- **No code changes.** No module moves, merges or new shared helpers. Sibling changes do that work.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `project-documentation`: adds a requirement that AGENTS.md states the backend
  code-organisation guideline and does not present data-flow facts or URL namespacing as
  backend import boundaries.

## Impact

- **Text only.** `AGENTS.md` changes, and the `project-documentation` spec gains one requirement.
  There are no behaviour, API, schema or dependency changes.
- **Checked and left unchanged:** `README.md` ("News, Events, and Weather are separate pipelines"
  describes data flow, and `project-documentation` requires it), `CONTRIBUTING.md` (it links to
  AGENTS.md for architecture and has no separation language), `docs/` (upstream API references
  only).
- **Not touched:** the `app-shell` requirement "Versioned feature-namespaced API surface" and the
  `frontend-shell` requirement "Feature-namespaced frontend source layout".
- **Ordering:** this change should merge before `consolidate-shared-helpers`,
  `extract-orm-base`, `unify-refresh-orchestration`, `add-typed-contracts`,
  `add-shared-http-client` and `tidy-small-inconsistencies`, which cite it or touch the same
  AGENTS.md text.
