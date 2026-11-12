## Context

LocalDash is a FastAPI app with a Svelte SPA served from the same origin. It can be exposed
publicly through an opt-in Cloudflare tunnel. Today it has no users, no sessions, no
middleware and no auth dependency; every "token" in `app/` is an upstream API credential.

This is the first of a series of small changes that build an authenticated admin section:

1. `add-admin-auth` (this change): accounts, login and access checks on the backend; a login
   page and an empty admin dashboard page on the frontend.
2. Next: refresh endpoints become admin-only and their buttons move to the dashboard.
3. Later: refresh run history, config management, content curation.

The frontend is a Svelte 5 SPA with a hand-rolled path router and four routes. It has no
notion of a signed-in user, a guarded route or a 401.

Constraints agreed with the project owner:

- User data lives in the database.
- Use popular, maintained libraries; do not hand-write security primitives.
- `fastapi-users` is ruled out because it is in maintenance mode.
- There is one kind of admin now. Other admin types and non-admin users may come later.

## Goals / Non-Goals

**Goals:**

- A `users` table and password login that work for any user, with admin as one flag.
- Revocable server-side sessions carried in an HttpOnly cookie.
- Two reusable dependencies, `current_user` and `require_admin`, for later changes.
- An operator CLI to create the first admin without a registration endpoint.
- Security behaviour pinned by tests, because the session code is ours.
- A login page and an admin-only dashboard page with no content, so later changes have a
  place to put admin UI.

**Non-Goals:**

- Gating any existing endpoint, including the three refresh endpoints.
- Dashboard content, and links to `/login` or `/admin` from the public pages.
- Roles or permissions beyond `is_superuser`.
- Registration, email verification, password reset, OAuth sign-in.
- Login rate limiting (see Risks).

## Decisions

### 1. FastAPI helpers + pwdlib + our own session code

`fastapi.security` supplies `OAuth2PasswordRequestForm` (parses the login form) and
`APIKeyCookie` (reads the session cookie and documents it in OpenAPI). `pwdlib[argon2]`
hashes and verifies passwords. The standard library's `secrets` and `hashlib` make and hash
session tokens. The glue (look up user, verify, create session, look up session, delete
session) is about 150 lines in `app/auth/`.

- *Alternative: `fastapi-users`.* It packages exactly this glue plus registration and reset
  flows, but it is in maintenance mode with a successor announced. Rejected by the owner.
- *Alternative: Authlib.* Actively maintained but it is an OAuth/OIDC library; it does not
  provide local password accounts. It remains an option for non-admin sign-in later.
- *Note:* `OAuth2PasswordRequestForm` needs `python-multipart`, a new dependency. A JSON
  body would avoid it, but the form helper is FastAPI's documented login shape and makes the
  endpoint usable from the generated API docs.

### 2. Opaque database sessions, not JWTs

Login generates `secrets.token_urlsafe(32)`, stores `sha256(token)` in `sessions` with the
user id and an expiry, and sends the raw token to the browser. Each request hashes the cookie
value and looks the row up.

- Logout and "set password" revoke sessions by deleting rows; a JWT cannot be revoked
  without a denylist table, which is the same lookup with more parts.
- No signing key to generate, store or rotate, and no PyJWT dependency.
- Only the hash is stored, so a database leak does not expose usable sessions. SHA-256
  without a salt is sufficient here because the token is 256 bits of randomness, not a
  human-chosen secret.
- Cost: one indexed primary-key lookup per authenticated request. Public requests carry no
  cookie and do no lookup.

### 3. Cookie transport, not a bearer header

The cookie is `localdash_session`, `HttpOnly`, `SameSite=Lax`, `Path=/`, with `Max-Age` equal
to the session lifetime and `Secure` controlled by the `auth_cookie_secure` setting
(default `true`).

- `HttpOnly` keeps the token out of reach of page JavaScript, so an XSS bug cannot steal it.
  `OAuth2PasswordBearer` would require the SPA to hold the token in JavaScript.
- The SPA and API share an origin, so the browser sends the cookie with no frontend code, and
  the WebSocket handshake carries it too if admin live updates are ever needed.
- `Secure` defaults on because the public deployment is HTTPS through the tunnel. Chrome and
  Firefox accept `Secure` cookies on `http://localhost`; the setting exists for plain-HTTP LAN
  access and for Safari on localhost.

### 4. CSRF: SameSite=Lax plus a "no state-changing GET" rule

`SameSite=Lax` stops the cookie being sent on cross-site POSTs, which covers every mutating
endpoint as long as none of them is a GET. That rule is stated in `AGENTS.md`. No CSRF token
is added.

- Login CSRF (an attacker logging the victim into the attacker's account) is not prevented.
  It is low impact here: accounts hold no personal data and the attacker gains nothing.

### 5. Data model

```
users
  id               uuid PK default gen_random_uuid()
  email            text NOT NULL UNIQUE, CHECK (email = lower(email))
  hashed_password  text NOT NULL
  is_active        boolean NOT NULL default true
  is_superuser     boolean NOT NULL default false
  created_at       timestamptz NOT NULL default now()

sessions
  token_hash       text PK            -- hex sha256 of the cookie token
  user_id          uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE
  created_at       timestamptz NOT NULL default now()
  expires_at       timestamptz NOT NULL, indexed
```

- The table is `users`, not `admins`, and the API is `/api/v1/auth/*`, so non-admin users
  need no rename later.
- `is_superuser` is the only privilege. A `role` column is deferred until a second admin type
  exists; adding it then is a trivial migration with a handful of rows.
- Email is the login identifier, normalised with `strip().lower()` on write and on login.
  It is not validated as deliverable (no `email-validator` dependency), since nothing sends
  mail yet.
- The migration is hand-written raw SQL like the others. `gen_random_uuid()` is built into
  Postgres 16.

### 6. Login behaviour

- Unknown email, wrong password and inactive account all return the same `401` with the same
  body. On the unknown-email path the code still verifies against a fixed dummy hash, so the
  response time does not reveal whether the email exists.
- Password verification runs in `asyncio.to_thread`: argon2 is deliberately slow and must not
  block the event loop that also runs the poll jobs and the WebSocket.
- `pwdlib`'s `verify_and_update` returns a new hash when the stored one uses outdated
  parameters; login saves it.
- Success returns `204` with the `Set-Cookie` header. The body is empty; the SPA calls
  `/auth/me` for user details.

### 7. Session lifetime and lookup

- Fixed lifetime of `auth_session_days` (default 7) from login; no sliding renewal. Simpler
  to reason about and to test; sliding expiry can be added if weekly re-login is annoying.
- Lookup joins `sessions` to `users` and requires `expires_at > now` and `is_active`. A
  deactivated user loses access on the next request without touching their sessions.
- Lookup functions take a keyword-only `now`, matching the project's convention for
  time-dependent code.

### 8. Dependencies: 401 versus 403

- `current_user`: no cookie, unknown token, expired session or inactive user gives `401`.
- `require_admin`: builds on `current_user`; a valid non-admin user gives `403`.
- Both live in `app/auth/deps.py`. Nothing in this change uses `require_admin` on a real
  route, so tests mount it on a throwaway router.

### 9. Operator CLI

`python -m app.auth create-user --email <email> [--admin]` and
`python -m app.auth set-password --email <email>`. The password is read with `getpass`
(prompted twice) or from stdin when not a TTY, never from an argument, so it does not land in
shell history or the process list. Minimum length is 12 characters. `set-password` deletes
all of that user's sessions. Under Docker:
`docker compose exec app python -m app.auth create-user --email … --admin`.

- *Alternative: bootstrap the first admin from env vars at startup.* Rejected: it leaves a
  password in `.env` and adds startup logic that is only useful once.

### 10. Expired-session cleanup

One `JobSpec` in `app/scheduler.py` runs `app/auth/cleanup.py` hourly and deletes rows with
`expires_at < now`. Expired sessions are already rejected by the lookup, so the job only
bounds table growth. It is always registered; there is no `auth_enabled` switch.

### 11. Code layout

```
app/auth/
  __init__.py
  __main__.py     CLI entry point
  models.py       User, Session ORM models on the shared Base
  passwords.py    pwdlib wrapper: hash, verify_and_update, dummy verify
  sessions.py     create / lookup / delete / delete_expired
  deps.py         current_user, require_admin
  cleanup.py      the scheduled cycle
  schemas.py      UserOut
app/api/auth.py   login, logout, me
```

### 12. Two frontend features: `auth` and `admin`

```
frontend/src/features/auth/
  index.ts            LoginPage, authState(), loadUser(), logout(), User type
  api.ts              login (form-encoded POST), me, logout
  state.svelte.ts     { status: "unknown" | "anonymous" | "signedIn", user }
  components/LoginPage.svelte
frontend/src/features/admin/
  index.ts            AdminPage
  components/AdminPage.svelte
frontend/src/styles/auth.css, admin.css
```

- The split follows the existing rule that a feature folder mirrors an API namespace: `auth`
  matches `/api/v1/auth`, and `admin` will match `/api/v1/admin` when it exists. It also
  keeps login usable by non-admin users later without importing anything admin.
- `admin` imports only `auth`'s `index.ts`, as the import rules require.
- *Alternative: one `admin` feature holding the login page.* Fewer folders, but login would
  have to move out as soon as a non-admin user can sign in.

### 13. The signed-in user is loaded lazily

The auth state starts as `unknown`. `loadUser()` calls `GET /api/v1/auth/me` once and is
invoked only when `/login` or `/admin` is rendered; a `401` means `anonymous`.

- Public visitors never trigger the request, so the public pages make no extra call and log
  no `401` in the console.
- Consequence: the public header cannot show a "signed in" state or an Admin link. An admin
  opens `/admin` directly. A header link can be added when there is something to link to.

### 14. Route guard in the shell, with a history-replacing redirect

`App.svelte` gains two route entries. For `/admin` and `/login` it renders by auth state:

| Route | `unknown` | `anonymous` | signed in, admin | signed in, not admin |
|---|---|---|---|---|
| `/admin` | "Loading…" | redirect to `/login` | dashboard | "no access" message + log out |
| `/login` | "Loading…" | login form | redirect to `/admin` | redirect to `/` |

- `lib/router.svelte.ts` gains `redirect(to)`, which uses `history.replaceState`. With
  `pushState`, pressing Back from `/login` would land on `/admin` and bounce forward again.
- The guard is a convenience, not a security boundary: the admin page's code ships in the
  public bundle and anyone can read it. The boundary is `require_admin` on the API. The page
  holds no data in this change.
- The admin bundle is not lazy-loaded. It is a heading and a button today; code-splitting is
  worth adding when the admin UI has real weight.
- After a successful login the page calls `loadUser()` and the table above sends the user on.
  There is no "return to where you were" parameter, since `/admin` is the only guarded route.

### 15. Login page and dashboard page behaviour

- The login form posts `username` (the email) and `password` as
  `application/x-www-form-urlencoded`, which is what `OAuth2PasswordRequestForm` reads. The
  browser stores the cookie; no token touches JavaScript.
- A `401` shows one message, "Incorrect email or password", matching the backend's refusal
  to say which was wrong. Any other failure shows a generic "could not sign in" message. The
  submit button is disabled while a request is in flight.
- The inputs use `type="email"` / `type="password"` with `autocomplete="username"` /
  `"current-password"` so password managers work.
- The dashboard shows a heading, the signed-in email and a "Log out" button. Log out calls
  the API, sets the state to `anonymous` and redirects to `/login`.
- Both pages use the existing theme variables, so they work in every theme, and render the
  shared site footer like the other content pages.

## Risks / Trade-offs

- [The frontend has no test runner, so the guard table is checked by hand] → `npm run check`
  covers types, and task 9.3 walks every cell of the table in a browser.
- [We own the session code, so a logic bug is ours] → Keep it small, use only standard
  primitives, and pin each security property with a test (see specs).
- [No login rate limiting: password guessing is unthrottled, and each attempt costs an
  argon2 verify] → Passwords are at least 12 characters and the first deployment has one
  account. A Cloudflare rate-limit rule on `/api/v1/auth/login` is recommended in the docs.
  An in-app limiter is a separate proposal.
- [`pwdlib` / `argon2-cffi` may lack Python 3.14 wheels] → Task 1 installs and imports them
  under the project's 3.14 lock before any other work. If that fails, stop and revise this
  design (pwdlib's bcrypt backend is the fallback).
- [`pwdlib` shares an author with `fastapi-users`] → It is a separate, actively released
  package and is what FastAPI's own tutorial uses.
- [`Secure` cookie default breaks login over plain-HTTP LAN addresses] → `AUTH_COOKIE_SECURE`
  is documented in `.env.example`.
- [Registration, verification and reset will be our code when non-admin users arrive] →
  Accepted. OAuth sign-in through Authlib is an alternative to evaluate then.

## Migration Plan

- Deploy: the entrypoint already runs `alembic upgrade head`; the new migration only adds two
  tables. Then create the first admin with the CLI.
- Nothing on the existing pages changes; `/login` and `/admin` are new paths that were
  not-found pages before.
- Rollback: redeploy the previous image. The tables can stay (nothing else reads them) or be
  dropped with `alembic downgrade -1`.

## Open Questions

None blocking. Sliding session expiry and an in-app login limiter are deferred until there is
evidence they are needed.
