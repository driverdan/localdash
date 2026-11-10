## ADDED Requirements

### Requirement: AGENTS.md states the backend code-organisation guideline

The `AGENTS.md` guidance file SHALL state that the backend (`app/`) is one application whose
packages organise code but are not boundaries: any backend module may import from any other, and
reusing or promoting existing code is preferred over writing a second copy. It SHALL say that
feature separation still applies to data flow, to the `/api/v1/<feature>/` API namespaces with one
router module per feature in `app/api/`, and to the frontend's import rules, and that none of these
restricts backend imports. It SHALL give practical guidance on avoiding import cycles without
adding a list of forbidden imports or another boundary rule.

#### Scenario: The guideline is present

- **WHEN** an agent reads `AGENTS.md`
- **THEN** it finds a backend code-organisation guideline stating that backend packages are not
  boundaries and that any backend module may import from any other
- **AND** the guideline prefers reusing or promoting existing code over duplicating it

#### Scenario: Data-flow facts are not presented as import rules

- **WHEN** an agent reads the descriptions of News, Events, and Weather as sibling features that
  do not flow through collectors/ingest
- **THEN** those descriptions remain in `AGENTS.md`
- **AND** `AGENTS.md` states that they describe data flow, not restrictions on backend imports

#### Scenario: The frontend rules and API namespacing are unchanged

- **WHEN** an agent reads `AGENTS.md` after this guideline is added
- **THEN** the frontend import rules still restrict cross-feature imports to each feature's
  `index.ts` and still apply only to `frontend/src/`
- **AND** each feature still owns `/api/v1/<feature>/` and one router module in `app/api/`

#### Scenario: Import-cycle guidance is advice, not a boundary

- **WHEN** an agent reads the guideline's import-cycle guidance
- **THEN** it advises keeping shared code below the code that uses it and fixing a cycle by moving
  the shared part into a module both sides can import
- **AND** it does not forbid imports between backend packages
