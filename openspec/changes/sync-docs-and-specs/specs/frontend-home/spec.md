## MODIFIED Requirements

### Requirement: Home feature namespace
The home landing UI SHALL live in `frontend/src/features/home/`, following the established
feature layout (typed `api.ts` client, a runes store, components, and an `index.ts` public
surface exporting only the page component and its live-update registration function). It SHALL be mounted at the root route (`/`).
Cross-feature imports SHALL resolve only to other features' `index.ts` public surfaces (the
news feature's shared card component and the events feature's types), never to their internals.

#### Scenario: Home is an isolated feature
- **WHEN** imports under `frontend/src/features/home/` are inspected
- **THEN** every cross-feature import resolves to `features/news` or `features/events` public
  surfaces (`index.ts`), never to files inside those namespaces
