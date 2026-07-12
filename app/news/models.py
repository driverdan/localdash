"""SQLAlchemy ORM models for the news feature.

Three plain relational tables (no PostGIS/Timescale): the outlet registry
(news_sources -> news_feeds, upserted from registry.py at startup) and the
articles they produce. Cross-outlet story grouping lives in
news_articles.cluster_id, recomputed after every fetch (clustering.py).
"""
from __future__ import annotations

from datetime import datetime

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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class NewsSource(Base):
    __tablename__ = "news_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    homepage: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    feeds: Mapped[list["NewsFeed"]] = relationship(back_populates="source")


class NewsFeed(Base):
    __tablename__ = "news_feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("news_sources.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(Text, unique=True)
    # The sites' feed items carry no category tags; the section feed an article
    # appeared in supplies its category (see registry.py).
    category: Mapped[str] = mapped_column(String(32), default="news")
    position: Mapped[int] = mapped_column(Integer, default=0)

    # Per-feed fetch telemetry, surfaced in the UI sources footer.
    last_fetch: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped["NewsSource"] = relationship(back_populates="feeds")


class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint("source_id", "guid", name="uq_news_article_source_guid"),
        Index("ix_news_articles_published", "published"),
        Index("ix_news_articles_cluster", "cluster_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("news_sources.id", ondelete="CASCADE"))
    guid: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="news")
    published: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Same-story group id: the smallest member article id (clustering.py).
    cluster_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
