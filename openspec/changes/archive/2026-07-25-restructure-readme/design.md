## Context

`README.md` is 283 lines written incrementally as features landed, and it now
serves three audiences at once. Measured by line count and intended reader:

| Section | Lines | Reader |
| --- | ---: | --- |
| Intro + feature table | 15 | newcomer |
| Map — time-series deep dive | 40 | contributor |
| News | 12 | newcomer |
| Events | 14 | newcomer |
| Quick start (Docker) | 16 | newcomer |
| Quick start (local dev) | 28 | contributor |
| Cloudflare tunnel | 25 | operator |
| API — four endpoint tables | 39 | contributor |
| Adding a geo data source | 23 | contributor |
| Tests | 10 | contributor |
| Linting & formatting | 17 | contributor |
| Git workflow | 12 | agent |
| Notes | 11 | mixed |
| License | 8 | newcomer |

Roughly 60% is contributor material and it sits *above* the operational content a
newcomer needs. The contributor blocks are also near-duplicates of `AGENTS.md`
sections (data model ≈ `AGENTS.md:350`, adding a source ≈ `:357`, API conventions
≈ `:455`, git workflow ≈ `:150`), and it is the README's copies that have gone
stale.

### Drift audit

Every item below was verified against the code on this branch and is the
authoritative correction list for the implementation phase.

| README claim | Reality | Evidence |
| --- | --- | --- |
| "three sibling features" | Four backend features plus a Home page | `app/main.py:129-134` |
| News served at `/` | `/` is Home; News moved to `/news` | `frontend/src/App.svelte:20-23` |
| Weather unmentioned | Ships: NWS forecast + AirNow AQI, home strip | `app/weather/`, `app/api/weather.py` |
| Weather shown as a hypothetical `WeatherCollector` | Weather is a sibling feature with no DB tables and no scheduler job — *not* a collector | `AGENTS.md:434` |
| `X-Frontend-Auth` is a config secret | No such setting exists | `app/config.py` |
| Events sources omit `chattzoo` | `chattzoo.py` is a registered source | `app/events/sources/` |
| "Chattanooga outlets" (vague) | Eight registered outlets | `app/news/registry.py` |
| Site name is fixed | `SITE_NAME` is configurable; app is brandable | `app/config.py:20` |
| Theme switcher unmentioned | Ships in the header | `frontend/src/App.svelte` |
| AirNow air quality unmentioned | `airnow_api_key`, `airnow_stale_minutes` | `app/config.py:124-129` |

The existing `project-documentation` spec is stale in the same ways, and
additionally requires documenting a WebSocket at `/api/v1/timeseries/ws`; that
endpoint was removed and the bus now lives at `/api/v1/ws`
(`app/api/root.py:24`, and `app/main.py:81` describes the old path as removed).

## Goals / Non-Goals

**Goals:**

- A README aimed at one reader: someone who has just found the project and wants
  to know what it is, see it, and run it. Target ~100 lines.
- Every factual claim in the README true as of this change.
- Exactly one home for each piece of contributor material, with links rather than
  copies.
- An honest answer to "can I use this for my city?"

**Non-Goals:**

- Restructuring `AGENTS.md`. It is accurate and well-organized; this change edits
  it only where the delta spec forces a correction (feature count).
- Writing user-facing feature guides or per-source documentation. The
  reverse-engineered upstream API notes in `docs/` stay where they are.
- Any application code change. Docs and one image asset only.
- Building the multi-city support that the intro will describe as planned.

## Decisions

### 1. Human contributor docs move to `CONTRIBUTING.md`, not into `AGENTS.md`

Local-venv setup, `pytest`, and pre-commit are genuinely useful to a human and
should not require reading a file addressed to coding agents. `CONTRIBUTING.md`
is also the conventional filename GitHub surfaces in the PR and issue UI.

*Alternatives considered:* keeping a short duplicate Development section in the
README — rejected, duplication is the root cause of the current drift; and
linking straight into `AGENTS.md` — rejected, it buries human setup inside agent
process and reads as though contributions are agent-only.

`CONTRIBUTING.md` covers environment setup, tests, and linting, then links to
`AGENTS.md` for architecture and the OpenSpec three-PR git workflow rather than
restating either.

### 2. Keep the snapshot → time-series summary, drop the mechanism

The snapshot → time-series construction is the genuinely non-obvious idea in the
project and the reason it is not four RSS readers, so ~4 lines of it earn their
place as a hook. The hypertable partitioning, PostGIS geometry columns, JSONB
property bags, and the ASCII pipeline diagram are mechanism a newcomer cannot act
on, and `AGENTS.md:316-360` already explains them properly.

### 3. Replace the API tables with the served Swagger UI

`app/main.py:126` constructs `FastAPI(...)` without a `docs_url` override, so
Swagger UI is already live at `/docs` and OpenAPI JSON at `/openapi.json`. Thirty-
nine lines of hand-maintained tables that already omit `/api/v1/weather/current`
become one line pointing at a reference that cannot go stale. The spec
requirement mandating a README API reference is removed accordingly — replaced by
a requirement that the README point at the served docs.

*Alternative considered:* generating the tables from the OpenAPI schema at build
time — rejected as disproportionate tooling for a link.

### 4. Frame Chattanooga as current scope, multi-city as planned

The intro states plainly that LocalDash ships Chattanooga / Hamilton County
sources today, notes that presentation is already configurable (`SITE_NAME`,
`CENTER_LAT`/`CENTER_LON`, tile layer), and says multi-city support is planned.
This avoids both overclaiming a generic framework and implying the design is
permanently single-city.

### 5. Screenshot committed to the repo at `docs/images/`

One image of the Home page at the top of the README does more orientation work
than the feature table. It is committed rather than hot-linked so the README
renders offline and on forks. `docs/images/` keeps binary assets out of the repo
root. The Home page is the subject because it is what `/` now serves and it shows
several features at once.

*Trade-off:* a committed screenshot is one more thing that can go stale. Accepted
— a slightly dated screenshot still orients a reader, whereas a wrong route does
not.

### 6. Target README structure

```
README.md                                        ~100 lines
├── Title + one-paragraph what-it-is
├── Screenshot
├── Features            table: feature / route / what it does
├── How it works        ~4 lines: snapshot → time-series hook
├── Quick start         docker compose up --build
├── Configuration       .env.example pointers, SITE_NAME, center coords
├── Expose publicly     Cloudflare named tunnel (kept, lightly trimmed)
├── Contributing        → CONTRIBUTING.md, AGENTS.md, /docs
└── License             AGPL-3.0-or-later (kept)
```

Links out to: `CONTRIBUTING.md` (setup, tests, lint), `AGENTS.md` (architecture,
conventions, git workflow), `/docs` (live API reference), `docs/*.md`
(reverse-engineered upstream APIs).

## Risks / Trade-offs

- **The screenshot dates as the UI changes** → Accepted; it orients readers even
  when slightly behind, and the `project-documentation` spec already obliges docs
  updates in the same change as user-facing changes.
- **Contributors may not find `CONTRIBUTING.md`** → The README's Contributing
  section links to it directly, and GitHub surfaces the file in the PR and issue
  UI.
- **Removing the README API tables loses offline discoverability** → Acceptable;
  the tables were already incomplete, and `/docs` plus `openapi.json` are served
  by the app the reader is being told to start.
- **The delta spec removes a requirement rather than relaxing it** → Deliberate.
  Requiring a hand-maintained API reference is what produced the stale tables;
  the replacement requirement (point at the served docs) is the durable version.

## Migration Plan

Not applicable — documentation only, no deploy step and no runtime behavior
change. Reverting is a single `git revert`.

## Open Questions

None blocking. Two judgment calls are left to the implementation phase: the exact
wording of the multi-city statement, and whether the screenshot is captured in
light or dark theme (default light, since that is what an unconfigured first run
shows).
