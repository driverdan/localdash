## MODIFIED Requirements

### Requirement: Developer setup contract

The repository documentation (`AGENTS.md` and `CONTRIBUTING.md`) SHALL instruct
contributors to run `pre-commit install` once, and SHALL declare the tooling as
development dependencies: `pre-commit` in `pyproject.toml` `dev` extras, and
`prettier` plus `prettier-plugin-svelte` in `frontend/devDependencies`.

#### Scenario: New contributor enables hooks

- **WHEN** a contributor follows the documented setup steps
- **THEN** they install the dev dependencies and run `pre-commit install`, after
  which hooks fire on subsequent commits

#### Scenario: Setup instructions are reachable from the README

- **WHEN** a contributor starts from `README.md`
- **THEN** it links to `CONTRIBUTING.md`, where the `pre-commit install` step is
  documented
