# Frontend build stage: Node is needed only here, never in the runtime image.
FROM node:22-slim AS frontend

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# vite.config.ts builds to ../static -> /static in this stage.
RUN npm run build

# Dependency stage: builds /app/.venv from the committed uv.lock. Like the Node
# stage above, uv is a build-time tool only — the runtime image gets the venv it
# produced, never the uv binary itself.
FROM python:3.12-slim AS deps

# Pinned rather than :latest so a uv release can't silently change a build;
# Dependabot's docker ecosystem bumps this alongside the other base images.
COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /bin/uv

# copy: the venv is copied out to the next stage, so hardlinks into uv's cache
# would dangle. never: use this image's interpreter, don't fetch another.
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# --locked: build only from an in-sync lock — it errors if uv.lock disagrees with
# pyproject.toml. Note --frozen is NOT this: it installs the lock as-is and would
# happily build an image from a stale one.
# --no-editable: install the project as a real copy; an editable install would
# just be a link back to this stage's source tree.
# The dev deps are an extra (not a dependency group), so they stay out unless
# --extra dev is passed. asyncpg / psycopg[binary] ship wheels, so no compiler
# toolchain is needed.
COPY pyproject.toml uv.lock LICENSE README.md ./
COPY app ./app
RUN uv sync --locked --no-editable

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# The entrypoint calls `alembic` / `uvicorn` bare, so the venv leads the PATH.
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=deps /app/.venv ./.venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY --from=frontend /static ./static

COPY docker-entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
