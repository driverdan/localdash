## 1. Dependencies

- [x] 1.1 Add `pwdlib[argon2]` and `python-multipart` to `pyproject.toml` with bounded ranges, run `uv lock`, and confirm `uv sync --locked --extra dev` installs and `from pwdlib import PasswordHash` imports under Python 3.14. If argon2 wheels are unavailable, stop and revise the design before continuing.

## 2. Schema and models

- [x] 2.1 Add a hand-written raw-SQL Alembic migration creating `users` and `sessions` as in design decision 5 (lowercase-email CHECK, `ON DELETE CASCADE`, index on `sessions.expires_at`), with a downgrade that drops both.
- [x] 2.2 Add `app/auth/models.py` with `User` and `Session` ORM models on the shared `Base`, and import it where Alembic and the app load models.
- [x] 2.3 Add `auth_session_days` (default 7) and `auth_cookie_secure` (default true) to `Settings` and document `AUTH_SESSION_DAYS` / `AUTH_COOKIE_SECURE` in `.env.example`.

## 3. Passwords and sessions

- [x] 3.1 Add `app/auth/passwords.py`: hash, `verify_and_update`, and a dummy verify against a fixed hash, each run through `asyncio.to_thread`.
- [x] 3.2 Add `app/auth/sessions.py`: create (returns the raw token, stores its SHA-256 hash and expiry), lookup (unexpired session joined to an active user, keyword-only `now`), delete one, delete all for a user, delete expired.
- [x] 3.3 Add an email normalisation helper (`strip().lower()`) used by account creation and login.

## 4. API

- [x] 4.1 Add `app/auth/deps.py` with `current_user` (401) and `require_admin` (403) built on `APIKeyCookie(name="localdash_session", auto_error=False)`.
- [x] 4.2 Add `app/auth/schemas.py` (`UserOut`: id, email, is_superuser) and `app/api/auth.py` with `POST /login` (`OAuth2PasswordRequestForm`, identical 401 for unknown / wrong / inactive, hash upgrade on success, 204 + cookie), `POST /logout` (204, idempotent, clears cookie) and `GET /me`.
- [x] 4.3 Include the router in `app/main.py` at `/api/v1/auth`.

## 5. Operator CLI

- [x] 5.1 Add `app/auth/__main__.py` with `create-user --email [--admin]` and `set-password --email`: password from `getpass` (confirmed twice) or stdin when not a TTY, 12-character minimum, duplicate-email and unknown-email errors with a non-zero exit, and session revocation on `set-password`.

## 6. Session cleanup

- [x] 6.1 Add `app/auth/cleanup.py` (the cycle: own session, delete expired) and one hourly `JobSpec` in `job_specs()`.

## 7. Tests

- [x] 7.1 Accounts and passwords: case-insensitive unique email, non-admin default, stored value is an argon2 hash, outdated hash is upgraded on login.
- [x] 7.2 Login: success sets the cookie and creates a session; email matched case-insensitively; wrong password, unknown email and inactive account return identical status and body with no cookie or session; the unknown-email path performs a hash verification.
- [x] 7.3 Sessions: raw token absent from the row; expired, unknown-token and deactivated-user requests are unauthenticated (pin time with `now`).
- [x] 7.4 Cookie attributes with default settings and with `auth_cookie_secure` false (via `make_settings`).
- [x] 7.5 `/me` (200 without a password field, 401), logout (ends the session, 204 without a session, other sessions unaffected).
- [x] 7.6 `current_user` and `require_admin` on a throwaway router: 401 unauthenticated, 403 non-admin, handler runs for admin.
- [x] 7.7 CLI: create admin then log in, short password rejected, duplicate email rejected, `set-password` changes the password and deletes sessions; route listing shows only `login`, `logout`, `me` under `/api/v1/auth`.
- [x] 7.8 Cleanup deletes only expired sessions; the scheduler test covers the new job.

## 8. Frontend

- [x] 8.1 Add `redirect(to)` (History `replaceState`) to `frontend/src/lib/router.svelte.ts`.
- [x] 8.2 Add `frontend/src/features/auth/`: `api.ts` (form-encoded login, `me`, logout), `state.svelte.ts` (`unknown` / `anonymous` / `signedIn` plus the user, `loadUser()` that fetches once, `logout()`), and `index.ts` exporting the public surface.
- [x] 8.3 Add `LoginPage.svelte`: email and password inputs with autocomplete attributes, submit disabled while in flight, "Incorrect email or password" on 401, a generic message on other failures, `loadUser()` after success, and the shared site footer.
- [x] 8.4 Add `frontend/src/features/admin/` with `AdminPage.svelte` (heading, signed-in email, "Log out" button that logs out and redirects to `/login`, shared site footer) and `index.ts`; it imports only `auth`'s `index.ts`.
- [x] 8.5 Wire the shell: `/login` and `/admin` route entries in `App.svelte` following the guard table in design decision 14 (loading state, redirects, "no access" message with log out), and import `styles/auth.css` and `styles/admin.css` in `main.ts`.
- [x] 8.6 Write `auth.css` and `admin.css` using the existing theme variables; check both pages in the default and dark themes and at mobile width.

## 9. Docs and verification

- [ ] 9.1 Update `AGENTS.md` (auth package, cookie sessions, the two dependencies, the "no state-changing GET" rule, the CLI, the `auth` and `admin` frontend features, the `/login` and `/admin` routes and the guard) and `README.md` (creating the first admin, including the `docker compose exec` form, where to log in, and the recommended Cloudflare rate-limit rule on the login path).
- [ ] 9.2 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `npm run format:check`, `npm run check`, `npm run build` and `openspec validate add-admin-auth --strict`; all pass.
- [ ] 9.3 Rebuild with `docker compose up --build`, create an admin and a non-admin with the CLI in the container, and in a browser walk every cell of the guard table: `/admin` signed out redirects to `/login`; a wrong password shows the error; an admin login lands on `/admin`; Back does not bounce; `/login` while signed in redirects; the non-admin sees the "no access" message; log out returns to `/login` and `/admin` redirects again. Confirm the existing public pages and endpoints work without a cookie.
