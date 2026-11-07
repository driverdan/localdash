## Context

The audit compared every spec and doc against the code. `fix-audit-bugs` fixed the places where
the code was wrong. Everything left is text describing older behavior. This change has no runtime
effect, so the design records only the editorial decisions.

## Goals / Non-Goals

**Goals:**
- Every spec scenario and doc claim the audit flagged matches the shipped code.
- AGENTS.md is accurate for agent onboarding: routes, features, algorithms, jobs, CI, config.

**Non-Goals:**
- Any behavior change. Where the audit suggested a code change as an alternative (footer rows
  per outlet, `/sources` `enabled`, an empty-payload guard), the spec describes current behavior,
  and the code change is left for a future proposal.
- Rewriting docs that the audit did not flag.

## Decisions

- **The code is the reference.** Each correction describes what the code does today. The audit
  verified each item against `file:line`, and the implementer re-reads the code before editing.
- **Delta shape.** Wording fixes are MODIFIED requirements copied verbatim from the main spec and
  edited in place, so nothing unrelated changes at archive. New behavioral documentation, the
  timeseries closure sweep, is ADDED. The migration-era parity requirement is REMOVED with a reason.
  No requirement is renamed, which avoids the archive guard on renamed scenarios.
- **Purpose prose is edited at archive.** The OpenSpec CLI merges only requirements, so the
  `weather` Purpose ("no scheduler job") and the `events` Purpose (adding the Chattanooga Zoo) are
  hand-edited in the archive PR.
- **Status-label spec matches the code.** The audit noted the lookup is not source-aware. The
  spec now says so and requires codes with labels to be unique across sources. Making the lookup
  source-aware buys nothing while no codes collide.
- **TDOT doc.** The "LocalDash mapping" section is rewritten to describe the shipped single `tdot`
  collector. The upstream API description stays, because it is still accurate and useful.
- **`.prettierignore`.** Prettier reads the ignore file from its working directory, and both the
  hook and `npm run format` run in `frontend/`, so the file moves there. Its root-relative entries
  are rewritten relative to `frontend/`.

## Risks / Trade-offs

- **Docs drift again.** This is a snapshot fix. → `project-documentation` already obliges
  same-change doc updates; the AGENTS.md fixes make that baseline accurate again.
- **A spec now documents behavior that may be unwanted**, such as an empty payload closing every
  entity. → Documenting it makes it visible and testable; changing it is a separate decision.
