"""events feature: events, event_links, tags, event_tags, geocode_cache

Plain relational tables (no Timescale — events are not time-series), except the
PostGIS point on events.location. Kept as raw SQL to match the project's
migration convention.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE events (
            id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            canonical_key VARCHAR(64) NOT NULL UNIQUE,
            title         TEXT NOT NULL,
            description   TEXT NOT NULL DEFAULT '',
            starts_at     TIMESTAMPTZ NOT NULL,
            ends_at       TIMESTAMPTZ,
            venue_name    TEXT,
            address       TEXT,
            location      GEOMETRY(POINT, 4326),
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_events_starts_at ON events (starts_at)")
    op.execute("CREATE INDEX ix_events_location ON events USING GIST (location)")

    op.execute(
        """
        CREATE TABLE event_links (
            id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            event_id        BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            source_name     VARCHAR(128) NOT NULL,
            source_url      TEXT NOT NULL,
            source_event_id TEXT,
            CONSTRAINT uq_event_link_source UNIQUE (event_id, source_name)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE tags (
            id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name VARCHAR(64) NOT NULL UNIQUE
        )
        """
    )

    op.execute(
        """
        CREATE TABLE event_tags (
            event_id BIGINT  NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            tag_id   INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (event_id, tag_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE geocode_cache (
            id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            address    TEXT NOT NULL UNIQUE,
            latitude   DOUBLE PRECISION,
            longitude  DOUBLE PRECISION,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS geocode_cache")
    op.execute("DROP TABLE IF EXISTS event_tags")
    op.execute("DROP TABLE IF EXISTS tags")
    op.execute("DROP TABLE IF EXISTS event_links")
    op.execute("DROP TABLE IF EXISTS events")
