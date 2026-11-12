"""DB-backed tests for accounts, password login, sessions, the access-check
dependencies, the operator CLI and the expired-session cleanup.

Requests go through the ASGI app against the run's emptied temporary database
(see conftest.py). Clients use an https base URL so the cookie jar accepts the
default `Secure` cookie; tests that replay a cookie after logout send it by hand.
"""

from __future__ import annotations

import hashlib
import io
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import Depends, FastAPI
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import func, select, text, update

from app.auth import __main__ as cli
from app.auth.accounts import AccountError, create_user
from app.auth.cleanup import cleanup_sessions
from app.auth.deps import SESSION_COOKIE, current_user, require_admin
from app.auth.models import Session, User
from app.auth.sessions import create_session, lookup_session
from app.config import get_settings
from app.main import app
from tests.conftest import REPO_ROOT, make_settings

EMAIL = "admin@example.com"
PASSWORD = "correct horse battery staple"
T0 = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
WEEK = 7 * 24 * 60 * 60


@pytest.fixture
def auth_settings():
    """Settings the app's routes see; a test may replace it before requesting `client`."""
    return make_settings()


@pytest.fixture
async def client(db_session, auth_settings):
    app.state.collectors = {}
    app.dependency_overrides[get_settings] = lambda: auth_settings
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="https://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_settings, None)


async def _add_user(db, email=EMAIL, password=PASSWORD, *, admin=False, active=True) -> User:
    user = await create_user(db, email, password, is_superuser=admin)
    user.is_active = active
    await db.commit()
    return user


async def _login(client, username=EMAIL, password=PASSWORD) -> httpx.Response:
    return await client.post(
        "/api/v1/auth/login", data={"username": username, "password": password}
    )


async def _login_token(client, username=EMAIL, password=PASSWORD) -> str:
    """Log in and return the session token, leaving the client's cookie jar empty."""
    response = await _login(client, username, password)
    assert response.status_code == 204, response.text
    token = response.cookies[SESSION_COOKIE]
    client.cookies.clear()
    return token


def _cookie(token: str) -> dict[str, str]:
    return {"Cookie": f"{SESSION_COOKIE}={token}"}


async def _session_count(db) -> int:
    return (await db.execute(select(func.count()).select_from(Session))).scalar_one()


async def _stored_hash(db, email=EMAIL) -> str:
    return (await db.execute(select(User.hashed_password).where(User.email == email))).scalar_one()


def _cookie_attributes(response: httpx.Response) -> dict[str, str]:
    """The Set-Cookie attributes after name=value, keys lowercased (flags map to "")."""
    [header] = response.headers.get_list("set-cookie")
    _, *attrs = header.split("; ")
    parsed = {}
    for attr in attrs:
        key, _, value = attr.partition("=")
        parsed[key.lower()] = value
    return parsed


# --- accounts and passwords -------------------------------------------------------


async def test_email_is_unique_regardless_of_case(db_session):
    await _add_user(db_session)

    with pytest.raises(AccountError):
        await create_user(db_session, "Admin@Example.com", PASSWORD)
    await db_session.rollback()

    assert (await db_session.execute(select(User.email))).scalars().all() == [EMAIL]


async def test_email_is_stored_normalised(db_session):
    await _add_user(db_session, email="  Someone@Example.COM ")

    assert (await db_session.execute(select(User.email))).scalars().all() == ["someone@example.com"]


async def test_new_account_is_active_and_not_admin_by_default(db_session):
    await create_user(db_session, EMAIL, PASSWORD)
    await db_session.commit()

    row = (await db_session.execute(select(User.is_active, User.is_superuser))).one()
    assert tuple(row) == (True, False)


async def test_stored_password_is_an_argon2_hash(db_session):
    await _add_user(db_session)

    stored = await _stored_hash(db_session)
    assert stored.startswith("$argon2id$")
    assert PASSWORD not in stored
    assert Argon2Hasher().verify(PASSWORD, stored)


async def test_lowercase_email_is_enforced_by_the_table(db_session):
    with pytest.raises(Exception, match="ck_users_email_lowercase"):
        await db_session.execute(
            text("INSERT INTO users (email, hashed_password) VALUES ('Upper@Example.com', 'x')")
        )


async def test_outdated_hash_is_upgraded_on_login(client, db_session):
    weak = Argon2Hasher(time_cost=1, memory_cost=8192, parallelism=1).hash(PASSWORD)
    db_session.add(User(email=EMAIL, hashed_password=weak))
    await db_session.commit()

    response = await _login(client)

    assert response.status_code == 204
    upgraded = await _stored_hash(db_session)
    assert upgraded != weak
    assert not Argon2Hasher().check_needs_rehash(upgraded)
    assert Argon2Hasher().verify(PASSWORD, upgraded)


# --- login ----------------------------------------------------------------------


async def test_login_sets_cookie_and_creates_session(client, db_session):
    user = await _add_user(db_session)

    response = await _login(client)

    assert response.status_code == 204
    assert response.content == b""
    token = response.cookies[SESSION_COOKIE]
    rows = (await db_session.execute(select(Session.user_id, Session.token_hash))).all()
    assert [tuple(r) for r in rows] == [(user.id, hashlib.sha256(token.encode()).hexdigest())]


async def test_login_matches_email_case_insensitively(client, db_session):
    await _add_user(db_session)

    response = await _login(client, username=" Admin@Example.com ")

    assert response.status_code == 204
    assert SESSION_COOKIE in response.cookies


async def test_failed_logins_are_indistinguishable(client, db_session, monkeypatch):
    await _add_user(db_session)
    await _add_user(db_session, email="off@example.com", active=False)

    verifies = []
    original_verify = Argon2Hasher.verify

    def counting_verify(self, password, hash):
        verifies.append(hash)
        return original_verify(self, password, hash)

    monkeypatch.setattr(Argon2Hasher, "verify", counting_verify)

    wrong = await _login(client, password="not the password at all")
    unknown_before = len(verifies)
    unknown = await _login(client, username="nobody@example.com")
    unknown_verifies = len(verifies) - unknown_before
    inactive_before = len(verifies)
    inactive = await _login(client, username="off@example.com")
    inactive_hashes = verifies[inactive_before:]
    off_hash = await _stored_hash(db_session, "off@example.com")

    for response in (wrong, unknown, inactive):
        assert response.status_code == 401
        assert response.content == wrong.content
        assert "set-cookie" not in response.headers
    assert wrong.json() == {"detail": "Incorrect email or password"}
    # The unknown-email path still spends an argon2 verification.
    assert unknown_verifies == 1
    # An inactive account's password is never checked: one verification, against
    # the dummy hash, even though the password given was the right one.
    assert len(inactive_hashes) == 1
    assert inactive_hashes[0] != off_hash
    assert await _session_count(db_session) == 0


# --- sessions -------------------------------------------------------------------


async def test_raw_token_is_not_stored(client, db_session):
    await _add_user(db_session)

    token = await _login_token(client)

    row = (await db_session.execute(text("SELECT * FROM sessions"))).one()
    assert all(token not in str(value) for value in row)
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()


async def test_token_has_at_least_256_bits(client, db_session):
    await _add_user(db_session)

    token = await _login_token(client)

    # token_urlsafe(32): 32 random bytes, base64url without padding.
    assert len(token) >= 43


async def test_lookup_respects_expiry_with_pinned_now(db_session):
    user = await _add_user(db_session)
    token = await create_session(db_session, user.id, lifetime=timedelta(days=7), now=T0)
    await db_session.commit()

    found = await lookup_session(db_session, token, now=T0 + timedelta(days=6, hours=23))
    assert found is not None and found.id == user.id
    assert await lookup_session(db_session, token, now=T0 + timedelta(days=7)) is None
    assert await lookup_session(db_session, token, now=T0 + timedelta(days=8)) is None


async def test_expired_session_is_unauthenticated(client, db_session):
    user = await _add_user(db_session)
    token = await create_session(
        db_session, user.id, lifetime=timedelta(days=7), now=datetime.now(UTC) - timedelta(days=8)
    )
    await db_session.commit()

    response = await client.get("/api/v1/auth/me", headers=_cookie(token))

    assert response.status_code == 401


async def test_unknown_token_is_unauthenticated(client, db_session):
    await _add_user(db_session)
    await _login_token(client)

    response = await client.get("/api/v1/auth/me", headers=_cookie("not-a-real-token"))

    assert response.status_code == 401


async def test_deactivated_user_loses_access(client, db_session):
    user = await _add_user(db_session)
    token = await _login_token(client)
    assert (await client.get("/api/v1/auth/me", headers=_cookie(token))).status_code == 200

    await db_session.execute(update(User).where(User.id == user.id).values(is_active=False))
    await db_session.commit()

    assert (await client.get("/api/v1/auth/me", headers=_cookie(token))).status_code == 401


# --- cookie attributes ----------------------------------------------------------


async def test_cookie_attributes_with_default_settings(client, db_session):
    await _add_user(db_session)

    attrs = _cookie_attributes(await _login(client))

    assert attrs["httponly"] == ""
    assert attrs["samesite"].lower() == "lax"
    assert attrs["path"] == "/"
    assert attrs["secure"] == ""
    assert attrs["max-age"] == str(WEEK)


@pytest.mark.parametrize("auth_settings", [make_settings(auth_cookie_secure=False)])
async def test_cookie_without_secure_when_disabled(client, db_session, auth_settings):
    await _add_user(db_session)

    attrs = _cookie_attributes(await _login(client))

    assert "secure" not in attrs
    assert attrs["httponly"] == ""
    assert attrs["samesite"].lower() == "lax"
    assert attrs["path"] == "/"
    assert attrs["max-age"] == str(WEEK)


@pytest.mark.parametrize("auth_settings", [make_settings(auth_session_days=2)])
async def test_session_lifetime_follows_setting(client, db_session, auth_settings):
    await _add_user(db_session)
    before = datetime.now(UTC)

    attrs = _cookie_attributes(await _login(client))

    assert attrs["max-age"] == str(2 * 24 * 60 * 60)
    expires_at = (await db_session.execute(select(Session.expires_at))).scalar_one()
    assert timedelta(days=2) <= expires_at - before < timedelta(days=2, minutes=1)


# --- /me and logout -------------------------------------------------------------


async def test_me_returns_the_user_without_password(client, db_session):
    user = await _add_user(db_session, admin=True)
    token = await _login_token(client)

    response = await client.get("/api/v1/auth/me", headers=_cookie(token))

    assert response.status_code == 200
    assert response.json() == {"id": str(user.id), "email": EMAIL, "is_superuser": True}
    assert b"password" not in response.content


async def test_me_without_cookie_is_401(client, db_session):
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


async def test_logout_ends_the_session(client, db_session):
    await _add_user(db_session)
    token = await _login_token(client)

    response = await client.post("/api/v1/auth/logout", headers=_cookie(token))

    assert response.status_code == 204
    attrs = _cookie_attributes(response)
    assert attrs["max-age"] == "0"  # cleared
    assert attrs["path"] == "/"
    assert await _session_count(db_session) == 0
    assert (await client.get("/api/v1/auth/me", headers=_cookie(token))).status_code == 401


async def test_logout_without_session_is_204(client, db_session):
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    assert (
        await client.post("/api/v1/auth/logout", headers=_cookie("stale-token"))
    ).status_code == 204


async def test_logout_leaves_other_sessions_valid(client, db_session):
    await _add_user(db_session)
    first = await _login_token(client)
    second = await _login_token(client)

    await client.post("/api/v1/auth/logout", headers=_cookie(first))

    assert (await client.get("/api/v1/auth/me", headers=_cookie(second))).status_code == 200
    assert await _session_count(db_session) == 1


# --- access-check dependencies --------------------------------------------------


@pytest.fixture
async def guarded(db_session):
    """A throwaway app with one current_user route and one require_admin route."""
    throwaway = FastAPI()

    @throwaway.get("/any")
    async def any_user(user: User = Depends(current_user)) -> dict[str, str]:
        return {"email": user.email}

    @throwaway.get("/admin")
    async def admin_only(user: User = Depends(require_admin)) -> dict[str, str]:
        return {"email": user.email}

    transport = httpx.ASGITransport(app=throwaway)
    async with httpx.AsyncClient(transport=transport, base_url="https://test") as c:
        yield c


async def _token_for(db, email, *, admin) -> str:
    user = await _add_user(db, email=email, admin=admin)
    token = await create_session(db, user.id, lifetime=timedelta(days=1))
    await db.commit()
    return token


@pytest.mark.parametrize("path", ["/any", "/admin"])
async def test_guarded_route_without_session_is_401(guarded, db_session, path):
    assert (await guarded.get(path)).status_code == 401
    assert (await guarded.get(path, headers=_cookie("bogus"))).status_code == 401


async def test_non_admin_on_admin_route_is_403(guarded, db_session):
    token = await _token_for(db_session, "user@example.com", admin=False)

    assert (await guarded.get("/admin", headers=_cookie(token))).status_code == 403
    response = await guarded.get("/any", headers=_cookie(token))
    assert response.status_code == 200
    assert response.json() == {"email": "user@example.com"}


async def test_admin_on_admin_route_runs_the_handler(guarded, db_session):
    token = await _token_for(db_session, EMAIL, admin=True)

    response = await guarded.get("/admin", headers=_cookie(token))

    assert response.status_code == 200
    assert response.json() == {"email": EMAIL}


# --- operator CLI ---------------------------------------------------------------


async def test_cli_create_admin_then_log_in(client, db_session, capsys):
    code = await cli.run(
        ["create-user", "--email", "Admin@Example.com", "--admin"], io.StringIO(PASSWORD + "\n")
    )

    assert code == 0
    assert PASSWORD not in capsys.readouterr().out
    row = (await db_session.execute(select(User.email, User.is_active, User.is_superuser))).one()
    assert tuple(row) == (EMAIL, True, True)
    assert (await _login(client)).status_code == 204


async def test_cli_create_user_defaults_to_non_admin(db_session):
    code = await cli.run(["create-user", "--email", EMAIL], io.StringIO(PASSWORD + "\n"))

    assert code == 0
    assert (await db_session.execute(select(User.is_superuser))).scalar_one() is False


@pytest.mark.parametrize("command", ["create-user", "set-password"])
async def test_cli_rejects_short_password(db_session, capsys, command):
    if command == "set-password":
        await _add_user(db_session)
    before = (await db_session.execute(select(User.email, User.hashed_password))).all()

    code = await cli.run([command, "--email", EMAIL], io.StringIO("elevenchars\n"))

    assert code == 1
    assert "at least 12 characters" in capsys.readouterr().err
    assert (await db_session.execute(select(User.email, User.hashed_password))).all() == before


async def test_cli_rejects_duplicate_email(db_session, capsys):
    await _add_user(db_session)
    stored = await _stored_hash(db_session)

    code = await cli.run(
        ["create-user", "--email", "ADMIN@example.com", "--admin"],
        io.StringIO("a different password\n"),
    )

    assert code == 1
    assert "already exists" in capsys.readouterr().err
    rows = (await db_session.execute(select(User.hashed_password, User.is_superuser))).all()
    assert [tuple(r) for r in rows] == [(stored, False)]


async def test_cli_set_password_unknown_email_fails(db_session, capsys):
    code = await cli.run(["set-password", "--email", EMAIL], io.StringIO(PASSWORD + "\n"))

    assert code == 1
    assert "no user" in capsys.readouterr().err


async def test_cli_set_password_changes_password_and_revokes_sessions(client, db_session):
    await _add_user(db_session)
    first = await _login_token(client)
    second = await _login_token(client)
    assert await _session_count(db_session) == 2

    new_password = "a brand new passphrase"
    code = await cli.run(["set-password", "--email", EMAIL], io.StringIO(new_password + "\n"))

    assert code == 0
    assert await _session_count(db_session) == 0
    for token in (first, second):
        assert (await client.get("/api/v1/auth/me", headers=_cookie(token))).status_code == 401
    assert (await _login(client)).status_code == 401
    assert (await _login(client, password=new_password)).status_code == 204


async def test_cli_runs_as_a_module(db_session):
    # End to end through `python -m app.auth`, password piped on stdin. The
    # subprocess inherits conftest's DATABASE_URL, so it writes the test database.
    result = subprocess.run(
        [sys.executable, "-m", "app.auth", "create-user", "--email", EMAIL, "--admin"],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        input=PASSWORD + "\n",
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert PASSWORD not in result.stdout + result.stderr
    assert (await db_session.execute(select(User.is_superuser))).scalar_one() is True


def test_only_login_logout_and_me_under_auth():
    auth_routes = sorted(
        (method.upper(), path)
        for path, ops in app.openapi()["paths"].items()
        if path.startswith("/api/v1/auth")
        for method in ops
    )

    assert auth_routes == [
        ("GET", "/api/v1/auth/me"),
        ("POST", "/api/v1/auth/login"),
        ("POST", "/api/v1/auth/logout"),
    ]


# --- cleanup --------------------------------------------------------------------


async def test_cleanup_deletes_only_expired_sessions(db_session):
    user = await _add_user(db_session)
    await create_session(db_session, user.id, lifetime=timedelta(hours=1), now=T0)
    keep = await create_session(db_session, user.id, lifetime=timedelta(days=7), now=T0)
    await db_session.commit()

    deleted = await cleanup_sessions(now=T0 + timedelta(hours=2))

    assert deleted == 1
    remaining = (await db_session.execute(select(Session.token_hash))).scalars().all()
    assert remaining == [hashlib.sha256(keep.encode()).hexdigest()]


async def test_deleting_a_user_cascades_to_sessions(db_session):
    user = await _add_user(db_session)
    await create_session(db_session, user.id, lifetime=timedelta(days=1))
    await db_session.commit()

    await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    await db_session.commit()

    assert await _session_count(db_session) == 0
