## Context

A Python architecture review found a lot of copy-pasted backend code and produced 13 refactoring
proposals. The owner's response was a policy decision, not a refactor: the backend is one
application, and its feature packages are for organisation, not boundaries. This change records
that decision. It moves no code.

The current state, as verified for this proposal:

- **No written rule** forbids cross-feature imports on the backend. AGENTS.md and
  `openspec/specs/` state an explicit separation rule only for the frontend (AGENTS.md "Import
  rules"; `frontend-shell` "Feature-namespaced frontend source layout"), plus URL namespacing
  (`app-shell` "Versioned feature-namespaced API surface").
- **The backend follows a separation convention anyway.** There are no imports between
  `app/news`, `app/events`, `app/weather` and `app/collectors`. Only orchestration code
  (`main.py`, `scheduler.py`, `app/api/*`) and the timeseries `ingest.py` reach into those
  packages.
- **Where the convention comes from.** AGENTS.md calls news, events and weather "sibling features"
  that "do not flow through collectors/ingest" (the feature list and the news and events
  sections). The frontend paragraph introduces its import rules as mirroring "the API's
  feature-namespace convention", and the API conventions say each feature is "one `APIRouter`
  module". Read together, these look like one code-separation rule that covers both halves of the
  app.
- **What the convention produced.** The User-Agent string is identical in `app/news/registry.py`
  and `app/events/sources/carcruisefinder.py`; the latter's module docstring cites the former as
  "precedent" instead of importing it. Both `app/ingest.py` and `app/events/ingest.py` build
  `SRID=4326;POINT(...)` strings. `app/news/classify.py` and `app/events/tagging.py` both
  implement case-insensitive keyword-substring matching over title and summary text.

## Goals / Non-Goals

**Goals:**
- AGENTS.md says plainly that backend packages are not boundaries, that any backend module may
  import from any other, and that reuse is preferred over copying.
- The data-flow facts stay in AGENTS.md, worded so they no longer read as import rules.
- Light guidance on import cycles, which become possible once cross-package imports are normal.

**Non-Goals:**
- Consolidating any duplicate code. `consolidate-shared-helpers` (PR #338), `extract-orm-base`
  (PR #334), `unify-refresh-orchestration` (PR #335), `add-typed-contracts` (PR #339) and
  `add-shared-http-client` (PR #337) do that work.
- Any change to the frontend: its import rules, its layout, or the `frontend-shell` requirement.
- Any change to the API contract: `/api/v1/<feature>/` namespacing and the `app-shell`
  requirement.
- Replacing the old implicit boundary with a new explicit one. No layering rule, no
  import-linter, no list of forbidden imports.

## Decisions

### 1. The guideline text

A new `### Backend code organisation` subsection in AGENTS.md's "Architecture — the big picture",
placed right before "API / frontend conventions" so it sits next to the conventions it
distinguishes itself from. Proposed wording:

> The backend (`app/`) is one application. Its packages (`app/news/`, `app/events/`,
> `app/weather/`, `app/collectors/`) and its top-level modules group code by feature to make it
> easier to find. They are not boundaries: any backend module may import from any other.
>
> Before writing a helper, constant or mechanism, look for an existing one anywhere in `app/`
> and reuse it. If it lives somewhere awkward for the new caller, promote it to a shared
> module (move it, then import it from both places) instead of copying it. Two copies of the
> same logic drift apart.
>
> Feature separation still holds in three places, and none of them is about backend imports:
> - **Data flow.** News, events and weather do not flow through collectors/ingest; each has
>   its own pipeline and tables (weather has none).
> - **The API.** Each feature owns `/api/v1/<feature>/` and one router module in `app/api/`.
> - **The frontend.** Its import rules (above) apply to `frontend/src/` only.
>
> **Import cycles.** Shared code should sit below the code that uses it. Entry and orchestration
> modules (`main.py`, `scheduler.py`, `app/api/`) import feature code; feature code should not
> import them. When two modules need each other's code, move the shared part into a module both
> can import, rather than adding a function-local import. This is advice for fixing a cycle,
> not a list of forbidden imports.

**Why this wording:** it states the decision ("not boundaries", "any … may import from any
other"), gives the action the decision is meant to produce ("reuse or promote"), and lists what
does stay separate, so a reader does not mistake the data-flow facts for an import rule.

**Alternative considered:** a single sentence ("backend packages may import each other"). It is
too easy to miss beside the much longer frontend rules, and it does not name what still holds,
so the "sibling feature" wording could keep being read as a boundary.

### 2. Reword, do not delete, the data-flow facts

"Sibling feature" and "does not flow through collectors/ingest" are accurate statements about the
data model, and the `project-documentation` scenario "Non-collector features are described as
siblings" requires the README to keep saying so. They stay. The implementation makes two small
edits so that they no longer read as import rules:

- In the feature list, the first "sibling feature" mention (News) gets a short parenthetical that
  sibling refers to the data pipeline, with a pointer to "Backend code organisation". The Events
  and Weather mentions are left as they are.
- The frontend paragraph's lead-in, "The frontend mirrors the API's feature-namespace
  convention", becomes wording that says the frontend lays out its source by the API's feature
  namespaces and adds import rules of its own. The rules after "**Import rules:**" are not edited.
  The matching sentence under "API / frontend conventions" ("mirrors the namespace convention")
  gets the same treatment.

**Alternative considered:** dropping "sibling" altogether. Rejected: it is a useful word for the
data flow, and the README spec relies on the idea.

### 3. The spec delta goes in `project-documentation`

The obligation here is "AGENTS.md says X". `project-documentation` already owns AGENTS.md accuracy
("AGENTS.md matches the shipped app"), so one ADDED requirement fits there.

- **Not `app-shell`.** That spec is the runtime API contract. A code-organisation rule there would
  mix an API contract with a code-style rule, and that mix is what turned URL namespacing into an
  assumed import boundary. `consolidate-shared-helpers` is being revised to drop the `app-shell`
  requirement it had added ("Features SHALL NOT import another feature's internals") for the same
  reason. This change owns the general statement; that change keeps only "exactly one
  implementation of each helper" and cites this one.
- **Not `contributor-documentation`.** That spec requires `CONTRIBUTING.md` to link to AGENTS.md
  for architecture rather than restate it, so the guideline belongs in AGENTS.md.
- **ADDED, not MODIFIED.** "AGENTS.md matches the shipped app" is about current features and
  collectors. Adding a separate requirement leaves that one untouched and avoids the archive
  guard on renamed scenarios.

### 4. Import cycles: advice, not a rule

Cross-package imports make cycles possible. Today the dependency direction is clean: `main.py`,
`scheduler.py` and `app/api/*` import feature packages, and feature packages import only
`config`, `db`, `models`, `ws`, `redaction` and their own modules. The guidance says to keep shared
code below its users and to fix a cycle by moving the shared part down. It does not forbid
specific imports or add a check. The owner asked that the old implicit boundary not be replaced by
a new explicit one, and at this size a cycle shows up as an `ImportError` at startup, which the
test suite catches.

## Risks / Trade-offs

- **[Free imports turn into a tangle]** → The reuse-or-promote advice pushes shared code into
  shared modules instead of reaching into another feature's internals, and the cycle guidance
  keeps orchestration on top. A tangle that does appear is easy to see in review.
- **[Readers keep treating "sibling" as a boundary]** → The guideline says outright that data-flow
  separation is not an import rule, and the first "sibling" mention points to it.
- **[Overlap with `tidy-small-inconsistencies` (PR #332)]** → That change also adds backend
  conventions (logger names, parser placement) to AGENTS.md. Landing this change first gives it a
  "Backend code organisation" section to add to, instead of a second, overlapping section.
- **[Ordering with sibling PRs]** → This change should merge before every sibling change listed
  above. If one merges first, its AGENTS.md text may need a small rebase; nothing breaks at
  runtime.

## Open Questions

- Should the guideline name a default home for promoted helpers (a top-level `app/<name>.py`
  module, or an `app/shared/` package)? This proposal leaves it to `consolidate-shared-helpers`,
  which is the change that creates those modules.
- Should the README's "separate pipelines" sentence get the same clarification? This proposal
  says no: it is a newcomer's data-flow summary, it does not mention code, and a spec scenario
  requires it.
