"""Shared test fixtures.

Database-backed tests never touch the app's database. Each pytest run gets its
own temporary database (`localdash_test_<epoch>_<rand>`) on the server named by
the configured DATABASE_URL: created and migrated on first use, emptied before
every DB-backed test, and dropped when the run ends.
"""

from __future__ import annotations

# --- Temporary-database URL override -------------------------------------------
# This block MUST stay above every other `app.*` import. app/db.py builds its
# global engine/SessionLocal at import time from get_settings(), so pointing
# DATABASE_URL at the temporary database before anything imports app.db is what
# keeps app code that opens its own sessions (refresh(), the scheduler) off the
# real database. Environment variables take precedence over .env, so every
# get_settings()/Settings() in the run resolves to the temporary database.
import os
import secrets
import time

from sqlalchemy.engine import make_url

from app.config import Settings, get_settings

TEST_DB_PREFIX = "localdash_test"
_ORIGINAL_URL = make_url(Settings().database_url)
TEST_DB_NAME = f"{TEST_DB_PREFIX}_{int(time.time())}_{secrets.token_hex(4)}"
os.environ["DATABASE_URL"] = _ORIGINAL_URL.set(database=TEST_DB_NAME).render_as_string(
    hide_password=False
)
get_settings.cache_clear()
# -------------------------------------------------------------------------------

import json  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import psycopg  # noqa: E402
import pytest  # noqa: E402
from psycopg import sql  # noqa: E402

FIXTURE_DIR = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).parent.parent

# A temporary database older than this can't belong to a run still in progress
# (the full suite takes minutes), so a later run may drop it.
STALE_AFTER_SECONDS = 60 * 60

# Never truncated: Alembic's revision marker and PostGIS's reference table.
_KEEP_TABLES = {"alembic_version", "spatial_ref_sys"}
_truncate_tables: list[str] | None = None


def _assert_test_database(name: str) -> None:
    """Refuse any destructive operation on a database that isn't a test DB."""
    if not name.startswith(TEST_DB_PREFIX):
        raise RuntimeError(
            f"refusing to modify database {name!r}: test databases must start "
            f"with {TEST_DB_PREFIX!r}"
        )


def _connect(database: str) -> psycopg.Connection:
    """Sync autocommit connection to `database` on the configured server."""
    return psycopg.connect(
        host=_ORIGINAL_URL.host,
        port=_ORIGINAL_URL.port,
        user=_ORIGINAL_URL.username,
        password=_ORIGINAL_URL.password,
        dbname=database,
        autocommit=True,
    )


def _drop_database(conn: psycopg.Connection, name: str) -> None:
    _assert_test_database(name)
    # FORCE ends leftover connections: the app engine's pool and TimescaleDB's
    # background workers would otherwise block the drop.
    conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


def _sweep_stale_databases(conn: psycopg.Connection) -> None:
    """Drop test databases left behind by runs that never reached teardown."""
    rows = conn.execute(
        "SELECT datname FROM pg_database WHERE datname LIKE %s",
        (f"{TEST_DB_PREFIX}\\_%",),
    ).fetchall()
    cutoff = time.time() - STALE_AFTER_SECONDS
    for (name,) in rows:
        parts = name[len(TEST_DB_PREFIX) + 1 :].split("_")
        if parts and parts[0].isdigit() and int(parts[0]) < cutoff:
            _drop_database(conn, name)


def _migrate() -> None:
    # A subprocess, not alembic.command in-process: alembic/env.py runs
    # logging.config.fileConfig, which would disable the loggers caplog tests use.
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade head failed on {TEST_DB_NAME}:\n{result.stdout}\n{result.stderr}"
        )


@pytest.fixture(scope="session")
def test_database() -> Iterator[str]:
    """Create and migrate this run's temporary database; drop it at session end.

    Not autouse: only DB-backed tests request it (through the DB fixtures), so
    pure tests run without Postgres. Any error here — server unreachable, no
    CREATE DATABASE privilege, failed migration — errors every DB-backed test
    instead of skipping it.
    """
    _assert_test_database(TEST_DB_NAME)
    with _connect("postgres") as conn:
        _sweep_stale_databases(conn)
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DB_NAME)))
    try:
        _migrate()
        from app.db import engine

        if engine.url.database != TEST_DB_NAME:
            raise RuntimeError(
                f"app.db engine points at {engine.url.database!r}, not {TEST_DB_NAME!r}: "
                "something imported app.db before conftest overrode DATABASE_URL"
            )
        yield TEST_DB_NAME
    finally:
        with _connect("postgres") as conn:
            _drop_database(conn, TEST_DB_NAME)


def _reset_database(name: str) -> None:
    """Empty every application table so the test sees only its own seeds."""
    global _truncate_tables
    _assert_test_database(name)
    with _connect(name) as conn:
        if _truncate_tables is None:
            rows = conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            ).fetchall()
            _truncate_tables = [t for (t,) in rows if t not in _KEEP_TABLES]
        if _truncate_tables:
            conn.execute(
                sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(
                    sql.SQL(", ").join(sql.Identifier(t) for t in _truncate_tables)
                )
            )


async def _db_session(test_database: str):
    """Reset the temporary database, then yield a session on it."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.db import engine as app_engine

    _reset_database(test_database)
    engine = create_async_engine(get_settings().database_url)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            yield session
    finally:
        await engine.dispose()
        # asyncpg connections are bound to the loop that opened them and every
        # test gets its own loop, so never let the app engine's pool carry a
        # connection into the next test.
        await app_engine.dispose()


@pytest.fixture
def hc911_payload() -> list[dict]:
    return json.loads((FIXTURE_DIR / "hc911_sample.json").read_text())


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
async def db_session(test_database):
    """Async session on the run's temporary database, emptied before the test."""
    async for session in _db_session(test_database):
        yield session


@pytest.fixture
async def events_db_session(test_database):
    """Async session on the run's temporary database for events tests."""
    async for session in _db_session(test_database):
        yield session


@pytest.fixture
async def news_db_session(test_database):
    """Async session on the run's temporary database for news tests."""
    async for session in _db_session(test_database):
        yield session
