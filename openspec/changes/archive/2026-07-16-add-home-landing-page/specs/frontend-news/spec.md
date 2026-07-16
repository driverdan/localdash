## MODIFIED Requirements

### Requirement: News feature namespace
The news UI SHALL live in `frontend/src/features/news/` (mirroring `/api/v1/news/`), following the
established feature layout (typed `api.ts` client, `types.ts`, a runes store, components, and an
`index.ts` public surface) and the shell's import rules: it imports only from itself, `lib/`, and
third-party packages, and consumers (the shell and other features) consume it only through
`index.ts`. It SHALL be mounted at route `/news`. The public surface SHALL additionally export the
`StoryCard` component, the `Story` type, and a category-label setter so the home feature can render
story digests without reaching into news internals.

#### Scenario: News is an isolated feature
- **WHEN** imports under `frontend/src/features/news/` are inspected
- **THEN** none resolve into `frontend/src/features/timeseries/` or any other feature

#### Scenario: News feed renders at /news
- **WHEN** the user navigates to `/news`
- **THEN** the full news feed (tabs, feed controls, sources footer) renders exactly as it
  previously did at `/`
