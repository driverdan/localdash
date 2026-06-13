"""initial schema: extensions, sources, entities, observations hypertable

Revision ID: 0001
Revises:
Create Date: 2026-06-13
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.execute(
        """
        CREATE TABLE sources (
            key                   VARCHAR(64) PRIMARY KEY,
            name                  VARCHAR(128) NOT NULL,
            enabled               BOOLEAN NOT NULL DEFAULT TRUE,
            poll_interval_seconds INTEGER NOT NULL DEFAULT 60,
            config                JSONB NOT NULL DEFAULT '{}'::jsonb,
            last_run_at           TIMESTAMPTZ,
            last_status           VARCHAR(32),
            last_error            TEXT,
            last_count            INTEGER
        )
        """
    )

    op.execute(
        """
        CREATE TABLE entities (
            id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source_key        VARCHAR(64) NOT NULL,
            external_id       VARCHAR(128) NOT NULL,
            category          VARCHAR(64) NOT NULL DEFAULT 'default',
            label             TEXT,
            first_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_active         BOOLEAN NOT NULL DEFAULT TRUE,
            last_geom         geometry(Point, 4326),
            latest_properties JSONB NOT NULL DEFAULT '{}'::jsonb,
            CONSTRAINT uq_entity_source_external UNIQUE (source_key, external_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_entities_source_key ON entities (source_key)")
    op.execute("CREATE INDEX ix_entity_active ON entities (source_key, is_active)")
    op.execute("CREATE INDEX ix_entities_last_geom ON entities USING gist (last_geom)")

    op.execute(
        """
        CREATE TABLE observations (
            entity_id   BIGINT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            observed_at TIMESTAMPTZ NOT NULL,
            source_key  VARCHAR(64) NOT NULL,
            category    VARCHAR(64) NOT NULL DEFAULT 'default',
            status      VARCHAR(64),
            geom        geometry(Point, 4326),
            properties  JSONB NOT NULL DEFAULT '{}'::jsonb,
            PRIMARY KEY (entity_id, observed_at)
        )
        """
    )

    # Turn observations into a TimescaleDB hypertable partitioned on observed_at.
    op.execute("SELECT create_hypertable('observations', 'observed_at')")
    op.execute("CREATE INDEX ix_obs_source_time ON observations (source_key, observed_at DESC)")
    op.execute("CREATE INDEX ix_obs_geom ON observations USING gist (geom)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS observations")
    op.execute("DROP TABLE IF EXISTS entities")
    op.execute("DROP TABLE IF EXISTS sources")
