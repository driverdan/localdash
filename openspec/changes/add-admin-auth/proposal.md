## Why

LocalDash has no authentication: every endpoint is public, including three `POST …/refresh`
endpoints that anyone on the Cloudflare tunnel can call. An admin section with CMS features
(an ops console, config management and content curation) is planned as a series of small
changes, and all of them need to know who is making a request. This change adds that
foundation and nothing else.

## What Changes

- Add user accounts stored in Postgres (`users` table): email, argon2 password hash, an active
  flag and an admin (`is_superuser`) flag. The table is for all users, not only admins;
  non-admin users are expected later.
- Add server-side sessions (`sessions` table): a random opaque token held by the browser in an
  HttpOnly cookie and stored hashed in the database, with a fixed expiry.
- Add `POST /api/v1/auth/login`, `POST /api/v1/auth/logout` and `GET /api/v1/auth/me`.
- Add two FastAPI dependencies for later changes to use: `current_user` (any active
  logged-in user, else 401) and `require_admin` (an admin, else 403).
- Add a CLI (`python -m app.auth`) to create a user and to set a password. There is no
  registration endpoint; accounts are created by an operator.
- Add a scheduled job that deletes expired sessions.
- Use maintained building blocks instead of hand-written primitives: FastAPI's
  `fastapi.security` helpers for request parsing, `pwdlib` (argon2) for password hashing and
  the standard library's `secrets` for tokens. `fastapi-users` was considered and rejected
  because it is in maintenance mode.

Not in this change (each is a later proposal):

- No frontend: no login page and no `/admin` route.
- No existing endpoint is gated. The refresh endpoints become admin-only in the dashboard
  change, which also moves their buttons out of the public debug panel.
- No roles beyond the admin flag, no registration, email verification or password reset, and
  no login rate limiting.

## Capabilities

### New Capabilities

- `auth`: user accounts, password login, server-side sessions, the current-user and
  admin-only access checks, operator account management and session cleanup.

### Modified Capabilities

None. No existing requirement changes; every current endpoint keeps its behaviour.

## Impact

- **Code**: new `app/auth/` package (models, password hashing, sessions, dependencies, CLI,
  cleanup cycle) and `app/api/auth.py` router; one `include_router` line in `app/main.py`; one
  `JobSpec` in `app/scheduler.py`; new settings in `app/config.py`.
- **Database**: one hand-written Alembic migration adding `users` and `sessions`.
- **API**: three new endpoints under `/api/v1/auth`. No existing endpoint changes.
- **Dependencies**: `pwdlib[argon2]` and `python-multipart` (required by FastAPI's
  `OAuth2PasswordRequestForm`), both added to `pyproject.toml` and `uv.lock`.
- **Configuration**: `AUTH_SESSION_DAYS` and `AUTH_COOKIE_SECURE`, documented in
  `.env.example`.
- **Docs**: `AGENTS.md` and `README.md` gain the auth feature and the create-user command.
- **Tests**: new DB-backed tests for accounts, login, sessions, the dependencies and the CLI.
