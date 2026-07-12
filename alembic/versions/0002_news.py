"""news feature: news_sources, news_feeds, news_articles

Plain relational tables (no PostGIS / Timescale). Kept as raw SQL to match the
project's migration convention.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE news_sources (
            id       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            slug     VARCHAR(64) NOT NULL UNIQUE,
            name     VARCHAR(128) NOT NULL,
            homepage TEXT NOT NULL,
            enabled  BOOLEAN NOT NULL DEFAULT TRUE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE news_feeds (
            id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source_id   INTEGER NOT NULL REFERENCES news_sources(id) ON DELETE CASCADE,
            url         TEXT NOT NULL UNIQUE,
            category    VARCHAR(32) NOT NULL DEFAULT 'news',
            position    INTEGER NOT NULL DEFAULT 0,
            last_fetch  TIMESTAMPTZ,
            last_status TEXT
        )
        """
    )

    op.execute(
        """
        CREATE TABLE news_articles (
            id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source_id  INTEGER NOT NULL REFERENCES news_sources(id) ON DELETE CASCADE,
            guid       TEXT NOT NULL,
            url        TEXT NOT NULL,
            title      TEXT NOT NULL,
            summary    TEXT NOT NULL DEFAULT '',
            category   VARCHAR(32) NOT NULL DEFAULT 'news',
            published  TIMESTAMPTZ NOT NULL,
            fetched_at TIMESTAMPTZ NOT NULL,
            cluster_id BIGINT,
            CONSTRAINT uq_news_article_source_guid UNIQUE (source_id, guid)
        )
        """
    )
    op.execute("CREATE INDEX ix_news_articles_published ON news_articles (published)")
    op.execute("CREATE INDEX ix_news_articles_cluster ON news_articles (cluster_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS news_articles")
    op.execute("DROP TABLE IF EXISTS news_feeds")
    op.execute("DROP TABLE IF EXISTS news_sources")
