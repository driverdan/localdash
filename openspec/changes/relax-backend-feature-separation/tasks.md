## 1. AGENTS.md guideline

- [ ] 1.1 Add a `### Backend code organisation` subsection to "Architecture — the big picture", right before "API / frontend conventions", using the wording in design.md decision 1: packages are not boundaries, any backend module may import from any other, reuse or promote instead of copying, what stays separate (data flow, API namespaces and routers, frontend rules), and the import-cycle advice
- [ ] 1.2 In the "What this is" feature list, add a short parenthetical to the News "sibling feature" mention saying that sibling refers to the data pipeline, with a pointer to "Backend code organisation". Leave the Events and Weather data-flow sentences as they are
- [ ] 1.3 Reword the lead-in of the frontend paragraph ("The frontend mirrors the API's feature-namespace convention") and the matching sentence under "API / frontend conventions" so that neither implies the backend has matching import rules. Do not edit the text after "**Import rules:**"

## 2. Checks

- [ ] 2.1 Confirm that `README.md`, `CONTRIBUTING.md` and `docs/` still contain no backend code-separation language (none was found when this change was proposed), and edit only if some has been added since
- [ ] 2.2 Confirm that the `app-shell` requirement "Versioned feature-namespaced API surface" and the `frontend-shell` requirement "Feature-namespaced frontend source layout" are unchanged, and that no file outside `AGENTS.md` changed
- [ ] 2.3 `pre-commit run --all-files` is clean and `openspec validate relax-backend-feature-separation --strict` passes
