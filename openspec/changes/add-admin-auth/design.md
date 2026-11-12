## Context

LocalDash is a FastAPI app with a Svelte SPA served from the same origin. It can be exposed
publicly through an opt-in Cloudflare tunnel. Today it has no users, no sessions, no
middleware and no auth dependency; every "token" in `app/` is an upstream API credential.

This is the first of a series of small changes that build an authenticated admin section:

1. `add-admin-auth` (this change): backend accounts, login and access checks.
2. `add-admin-dashboard`: login page, guarded `/admin` route, refresh endpoints admin-only.
3. Later: refresh run history, config management, content curation.

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

**Non-Goals:**

- Any frontend (login page, `/admin` route, 401 handling in the SPA).
- Gating any existing endpoint, including the three refresh endpoints.
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

## Risks / Trade-offs

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
- Nothing public changes, so there is no user-visible cutover.
- Rollback: redeploy the previous image. The tables can stay (nothing else reads them) or be
  dropped with `alembic downgrade -1`.

## Open Questions

None blocking. Sliding session expiry and an in-app login limiter are deferred until there is
evidence they are needed.
