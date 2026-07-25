# Contributing to LocalDash

Thanks for your interest in LocalDash. This guide covers setting up a local
development environment, running the tests, and the linting tools.

For how the app is put together internally — the architecture, the data model,
the API conventions, and the git workflow — see [`AGENTS.md`](AGENTS.md). It is
written for coding agents, but it is the authoritative reference for humans too,
and this guide deliberately links to it rather than repeating it.

## Development setup

The [quick start in the README](README.md#quick-start) runs everything in
Docker, which is the easiest way to see the app. For development you probably
want the opposite split: Postgres in Docker, the app from your own virtual
environment so `--reload` works.

You will need [uv](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

uv installs the exact dependency versions pinned in `uv.lock` — the same ones CI
and the Docker image use.

```bash
# 1. Database only (Postgres + PostGIS + TimescaleDB)
docker compose up -d db

# 2. Python env + dependencies (uv creates .venv)
uv sync --extra dev
source .venv/bin/activate

# 3. Config + migrations
cp .env.example .env          # DATABASE_URL points at localhost:5432
alembic upgrade head

# 4. Run the app
uvicorn app.main:app --reload
```

The app is now at <http://localhost:8000>, with interactive API docs at
<http://localhost:8000/docs>.

### Frontend

The frontend is Svelte + TypeScript in `frontend/`, built into `static/` where
the backend serves it.

```bash
cd frontend
npm install

npm run build    # one-off build, served by uvicorn at :8000
npm run dev      # or: hot-reload dev server at :5173, proxies /api to :8000
```

Use `npm run dev` while working on the frontend and `npm run build` when you want
to check the bundle the backend actually serves.

## Tests

```bash
pytest
```

Most tests are pure and offline — `normalize()`, the change-detection rule, news
clustering, and the weather payload shaping all run against saved fixtures in
`tests/fixtures/`.

Database-backed tests skip automatically unless `DATABASE_URL` points at a
reachable Postgres. To run them:

```bash
docker compose up -d db
alembic upgrade head
pytest
```

## Linting and formatting

A [pre-commit](https://pre-commit.com/) hook auto-fixes and lints **staged**
code — `ruff` for Python, `prettier` for the frontend. Hooks are not installed
automatically, so enable them once per clone:

```bash
uv sync --extra dev          # pre-commit + ruff
cd frontend && npm install   # prettier + prettier-plugin-svelte
pre-commit install           # from the repo root
```

If a hook reformats a file the commit **aborts** so you can review the change,
then re-stage and commit again — fixes are never committed unseen.

```bash
pre-commit run --all-files   # run across the whole tree
npm run format               # format the frontend directly (from frontend/)
```

Type-checking the frontend is a separate whole-project step, deliberately kept
out of the commit hook:

```bash
cd frontend && npm run check   # svelte-check
```

The hook is bypassable with `git commit --no-verify`, so treat it as a
convenience rather than a hard gate.

## Making a change

Never commit directly to `main` — every change starts on a branch and lands
through a pull request.

Changes large enough to warrant a written plan use the **OpenSpec** workflow in
`openspec/` and land as three sequential PRs (propose → implement → archive).
Both the branch/PR conventions and the OpenSpec lifecycle are specified in
[`AGENTS.md`](AGENTS.md#git-workflow-openspec-three-prs).

## Adding a data source

Adding a geo collector, a news outlet, or an events source is a small, contained
change in each case. The collector interface, the registration step, and the
per-feature source patterns are documented in
[`AGENTS.md`](AGENTS.md#adding-a-data-source).

The `docs/` directory holds reverse-engineered references for the upstream APIs
already integrated, which are a useful model when documenting a new one.

## License

LocalDash is licensed under the **GNU Affero General Public License v3.0 or
later**. By contributing, you agree that your contributions are licensed under
the same terms. See [LICENSE](LICENSE).
