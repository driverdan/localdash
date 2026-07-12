"""Shared test fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import Settings

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def hc911_payload() -> list[dict]:
    return json.loads((FIXTURE_DIR / "hc911_sample.json").read_text())


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
async def db_session():
    """Async session against the real DB; skips if unreachable."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import get_settings
    from app.models import Entity, Observation

    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"database not reachable: {exc}")

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        # Clean slate for the test source.
        await session.execute(
            Observation.__table__.delete().where(Observation.source_key == "test")
        )
        await session.execute(Entity.__table__.delete().where(Entity.source_key == "test"))
        await session.commit()
        yield session
    await engine.dispose()


@pytest.fixture
async def news_db_session():
    """Async session against the real DB for news tests; skips if unreachable.

    Cleans news rows belonging to sources whose slug starts with 'test-'
    (feeds/articles follow via ON DELETE CASCADE); real registry rows are
    left alone.
    """
    from sqlalchemy import delete, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.config import get_settings
    from app.news.models import NewsSource

    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"database not reachable: {exc}")

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        try:
            await session.execute(delete(NewsSource).where(NewsSource.slug.like("test-%")))
            await session.commit()
        except Exception as exc:  # noqa: BLE001 — table missing = migration not applied
            await engine.dispose()
            pytest.skip(f"news tables unavailable (run alembic upgrade head): {exc}")
        yield session
        await session.rollback()
        await session.execute(delete(NewsSource).where(NewsSource.slug.like("test-%")))
        await session.commit()
    await engine.dispose()
