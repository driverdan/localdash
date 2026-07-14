"""SQLAlchemy ORM models for the events feature.

An :class:`Event` is the canonical, de-duplicated event. Each origin that
reported it contributes an :class:`EventLink` (so every source is shown and
linked), and topics are many-to-many :class:`Tag` rows. Location is a PostGIS
point (SRID 4326), geocoded from the address; :class:`GeocodeCache` persists
every address lookup so no address is geocoded twice.
"""

from __future__ import annotations

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

event_tags = Table(
    "event_tags",
    Base.metadata,
    Column("event_id", BigInteger, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)

    events: Mapped[list["Event"]] = relationship(secondary=event_tags, back_populates="tags")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Stable hash that collapses the same event reported by multiple sources.
    canonical_key: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    venue_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    location = mapped_column(Geometry("POINT", srid=4326, spatial_index=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tags: Mapped[list[Tag]] = relationship(secondary=event_tags, back_populates="events")
    links: Mapped[list["EventLink"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventLink(Base):
    __tablename__ = "event_links"
    __table_args__ = (
        UniqueConstraint("event_id", "source_name", "source_url", name="uq_event_link_source_url"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("events.id", ondelete="CASCADE"))
    source_name: Mapped[str] = mapped_column(String(128))
    source_url: Mapped[str] = mapped_column(Text)
    source_event_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    event: Mapped[Event] = relationship(back_populates="links")


class GeocodeCache(Base):
    """Persisted address -> coordinates lookups so successes are never re-queried.

    A row with null coordinates records an address we tried but could not
    resolve; the refresh cycle's retry pass re-attempts such rows once their
    last_attempted_at is older than the configured retry age.
    """

    __tablename__ = "geocode_cache"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    address: Mapped[str] = mapped_column(Text, unique=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
