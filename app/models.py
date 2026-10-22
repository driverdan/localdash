"""SQLAlchemy ORM models — the source-agnostic geo time-series schema.

Three tables:
  * sources       — one row per registered data source + its last-run status.
  * entities      — one tracked thing per source (a 911 incident, later an APRS
                    station, a weather station). Holds the latest snapshot.
  * observations  — the time-series; a TimescaleDB hypertable on observed_at.

Source-specific fields live in the JSONB `properties` / `latest_properties`
columns, so a new source needs no schema change.
"""

from __future__ import annotations

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    poll_interval_seconds: Mapped[int] = mapped_column(Integer, default=60)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Last-run telemetry for the dashboard.
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("source_key", "external_id", name="uq_entity_source_external"),
        # The only is_active index (migration 0001); there is no standalone one.
        Index("ix_entity_active", "source_key", "is_active"),
        # Named explicitly (GIST) to match migrations 0001/0006; the column sets
        # spatial_index=False so GeoAlchemy2 doesn't also expect its own
        # auto-named idx_entities_last_geom.
        Index("ix_entities_last_geom", "last_geom", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64), default="default")
    label: Mapped[str | None] = mapped_column(Text, nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Generic geometry (Point for point sources, Polygon/MultiPolygon for area
    # sources like water advisories) — the geo stack is source-agnostic.
    last_geom = mapped_column(Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=True)
    # Fingerprint of last_geom used by ingest change-detection without ST_X/ST_Y
    # (which are point-only). Point form preserves the prior ~0.1 m threshold.
    geom_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_properties: Mapped[dict] = mapped_column(JSONB, default=dict)

    observations: Mapped[list["Observation"]] = relationship(back_populates="entity")


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        # ix_obs_source_time (source_key, observed_at DESC) is declared after the
        # class: the DESC needs the mapped column. Timescale's own
        # observations_observed_at_idx is created by create_hypertable() and is
        # excluded from autogenerate in alembic/env.py.
        # GIST spatial index, named explicitly; geom sets spatial_index=False so
        # GeoAlchemy2 doesn't expect a second, auto-named idx_observations_geom.
        Index("ix_obs_geom", "geom", postgresql_using="gist"),
    )

    entity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(64), default="default")
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    geom = mapped_column(Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=True)
    properties: Mapped[dict] = mapped_column(JSONB, default=dict)

    entity: Mapped["Entity"] = relationship(back_populates="observations")


# Timescale requires the partitioning column in the primary key, so per-source
# time-range scans (newest first, as /observations orders them) get their own
# index. Matches migration 0001 exactly, including the DESC.
Index("ix_obs_source_time", Observation.source_key, Observation.observed_at.desc())
