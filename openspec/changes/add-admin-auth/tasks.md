## 1. Dependencies

- [ ] 1.1 Add `pwdlib[argon2]` and `python-multipart` to `pyproject.toml` with bounded ranges, run `uv lock`, and confirm `uv sync --locked --extra dev` installs and `from pwdlib import PasswordHash` imports under Python 3.14. If argon2 wheels are unavailable, stop and revise the design before continuing.

## 2. Schema and models

- [ ] 2.1 Add a hand-written raw-SQL Alembic migration creating `users` and `sessions` as in design decision 5 (lowercase-email CHECK, `ON DELETE CASCADE`, index on `sessions.expires_at`), with a downgrade that drops both.
- [ ] 2.2 Add `app/auth/models.py` with `User` and `Session` ORM models on the shared `Base`, and import it where Alembic and the app load models.
- [ ] 2.3 Add `auth_session_days` (default 7) and `auth_cookie_secure` (default true) to `Settings` and document `AUTH_SESSION_DAYS` / `AUTH_COOKIE_SECURE` in `.env.example`.

## 3. Passwords and sessions

- [ ] 3.1 Add `app/auth/passwords.py`: hash, `verify_and_update`, and a dummy verify against a fixed hash, each run through `asyncio.to_thread`.
- [ ] 3.2 Add `app/auth/sessions.py`: create (returns the raw token, stores its SHA-256 hash and expiry), lookup (unexpired session joined to an active user, keyword-only `now`), delete one, delete all for a user, delete expired.
- [ ] 3.3 Add an email normalisation helper (`strip().lower()`) used by account creation and login.

## 4. API

- [ ] 4.1 Add `app/auth/deps.py` with `current_user` (401) and `require_admin` (403) built on `APIKeyCookie(name="localdash_session", auto_error=False)`.
- [ ] 4.2 Add `app/auth/schemas.py` (`UserOut`: id, email, is_superuser) and `app/api/auth.py` with `POST /login` (`OAuth2PasswordRequestForm`, identical 401 for unknown / wrong / inactive, hash upgrade on success, 204 + cookie), `POST /logout` (204, idempotent, clears cookie) and `GET /me`.
- [ ] 4.3 Include the router in `app/main.py` at `/api/v1/auth`.

## 5. Operator CLI

- [ ] 5.1 Add `app/auth/__main__.py` with `create-user --email [--admin]` and `set-password --email`: password from `getpass` (confirmed twice) or stdin when not a TTY, 12-character minimum, duplicate-email and unknown-email errors with a non-zero exit, and session revocation on `set-password`.

## 6. Session cleanup

- [ ] 6.1 Add `app/auth/cleanup.py` (the cycle: own session, delete expired) and one hourly `JobSpec` in `job_specs()`.

## 7. Tests

- [ ] 7.1 Accounts and passwords: case-insensitive unique email, non-admin default, stored value is an argon2 hash, outdated hash is upgraded on login.
- [ ] 7.2 Login: success sets the cookie and creates a session; email matched case-insensitively; wrong password, unknown email and inactive account return identical status and body with no cookie or session; the unknown-email path performs a hash verification.
- [ ] 7.3 Sessions: raw token absent from the row; expired, unknown-token and deactivated-user requests are unauthenticated (pin time with `now`).
- [ ] 7.4 Cookie attributes with default settings and with `auth_cookie_secure` false (via `make_settings`).
- [ ] 7.5 `/me` (200 without a password field, 401), logout (ends the session, 204 without a session, other sessions unaffected).
- [ ] 7.6 `current_user` and `require_admin` on a throwaway router: 401 unauthenticated, 403 non-admin, handler runs for admin.
- [ ] 7.7 CLI: create admin then log in, short password rejected, duplicate email rejected, `set-password` changes the password and deletes sessions; route listing shows only `login`, `logout`, `me` under `/api/v1/auth`.
- [ ] 7.8 Cleanup deletes only expired sessions; the scheduler test covers the new job.

## 8. Docs and verification

- [ ] 8.1 Update `AGENTS.md` (auth package, cookie sessions, the two dependencies, the "no state-changing GET" rule, the CLI) and `README.md` (creating the first admin, including the `docker compose exec` form, and the recommended Cloudflare rate-limit rule on the login path).
- [ ] 8.2 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` and `openspec validate add-admin-auth --strict`; all pass.
- [ ] 8.3 Rebuild with `docker compose up --build`, create an admin with the CLI in the container, and confirm login, `/me` and logout with `curl`, and that the existing public endpoints still respond without a cookie.
