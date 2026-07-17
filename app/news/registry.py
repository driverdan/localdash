"""News source/feed registry and category map (ported from ChattNews).

Code is the source of truth: sync_registry() upserts this into the DB at
startup and deletes feeds that were removed here, so editing this file is how
sources/feeds are added, disabled, or retired.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.news.models import NewsFeed, NewsSource

# A plain browser UA for feed requests: TownNews sites (Local 3) put unfamiliar
# UA strings in a near-zero rate-limit bucket and answer them with HTTP 429.
# Deliberately NOT the app-wide settings.user_agent used by the geo collectors.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"

# Normalized categories in display order. Each source section feed maps to one.
CATEGORIES = {
    "news": "News",
    "sports": "Sports",
    "business": "Business",
    "politics": "Politics",
    "opinion": "Opinion",
    "life": "Life",
}

# Local Chattanooga, TN news sources. Feeds verified 2026-07. Categorization is
# content-derived per article (see classify.py): a mapped feed <category> tag
# (only the two WordPress outlets — WDEF and the News Chronicle — emit per-item
# tags), else a keyword match, else a feed's registered category below as the
# fallback. List specific sections before the general news feed so that fallback
# prefers the specific category when an article appears in both.
SOURCES = [
    {
        "slug": "chattanoogan",
        "name": "Chattanoogan.com",
        "homepage": "https://www.chattanoogan.com",
        "enabled": True,
        "feeds": [
            {"category": "sports", "url": "https://www.chattanoogan.com/Sports/feed"},
            {"category": "opinion", "url": "https://www.chattanoogan.com/Opinion/feed"},
            {"category": "news", "url": "https://www.chattanoogan.com/Breaking-News/feed"},
        ],
    },
    {
        "slug": "timesfreepress",
        "name": "Chattanooga Times Free Press",
        "homepage": "https://www.timesfreepress.com",
        # The breakingnews feed is usually valid-but-empty; local/ is the one
        # that works. politics/life include syndicated national content —
        # known caveat, not a bug.
        "enabled": True,
        "feeds": [
            {"category": "sports", "url": "https://www.timesfreepress.com/rss/headlines/sports/"},
            {
                "category": "business",
                "url": "https://www.timesfreepress.com/rss/headlines/business/",
            },
            {
                "category": "politics",
                "url": "https://www.timesfreepress.com/rss/headlines/politics/",
            },
            {"category": "opinion", "url": "https://www.timesfreepress.com/rss/headlines/opinion/"},
            {"category": "life", "url": "https://www.timesfreepress.com/rss/headlines/life/"},
            {"category": "news", "url": "https://www.timesfreepress.com/rss/headlines/local/"},
        ],
    },
    {
        "slug": "wdef",
        "name": "WDEF News 12",
        "homepage": "https://wdef.com",
        # Category feeds live on www.wdef.com (the apex domain 301s).
        "enabled": True,
        "feeds": [
            {"category": "sports", "url": "https://www.wdef.com/category/sports/feed/"},
            {"category": "news", "url": "https://www.wdef.com/category/news/feed/"},
        ],
    },
    {
        "slug": "local3",
        "name": "Local 3 News (WRCB)",
        "homepage": "https://www.local3news.com",
        # TownNews search feeds; c= matches their site sections. Unfiltered
        # results mix in national CNN wire stories.
        "enabled": True,
        "feeds": [
            {
                "category": "sports",
                "url": (
                    "https://www.local3news.com/search/?f=rss&t=article"
                    "&c=local-sports*&l=25&s=start_time&sd=desc"
                ),
            },
            {
                "category": "news",
                "url": (
                    "https://www.local3news.com/search/?f=rss&t=article"
                    "&c=local-news&l=25&s=start_time&sd=desc"
                ),
            },
        ],
    },
    {
        "slug": "chattnewschronicle",
        "name": "Chattanooga News Chronicle",
        "homepage": "https://www.chattnewschronicle.com",
        # WordPress site. Only the primary feed is actively updated; the
        # per-category feeds are dormant, so all articles land under "news".
        "enabled": True,
        "feeds": [
            {"category": "news", "url": "https://www.chattnewschronicle.com/feed/"},
        ],
    },
    {
        "slug": "chattanoogapulse",
        "name": "The Pulse",
        "homepage": "https://www.chattanoogapulse.com",
        # Chattanooga's arts & entertainment weekly, on Metro Publisher. Only a
        # single global feed is exposed (the ?section= param is ignored), and
        # items carry no <category> tags, so all articles land under "life".
        "enabled": True,
        "feeds": [
            {"category": "life", "url": "https://www.chattanoogapulse.com/api/rss/content.rss"},
        ],
    },
    {
        "slug": "chattlibrary",
        "name": "Chattanooga Public Library",
        "homepage": "https://chattlibrary.org",
        # WordPress site. The News category feed is scoped to announcements;
        # the site-wide /feed/ is identical today but unscoped, and /news/feed/
        # is an empty WP page feed. Announcement/press-release content, so it
        # registers under "life" like The Pulse.
        "enabled": True,
        "feeds": [
            {"category": "life", "url": "https://chattlibrary.org/category/news/feed/"},
        ],
    },
]


async def sync_registry(session: AsyncSession) -> None:
    """Upsert SOURCES into the DB; delete feeds removed from the registry."""
    for src in SOURCES:
        stmt = pg_insert(NewsSource).values(
            slug=src["slug"],
            name=src["name"],
            homepage=src["homepage"],
            enabled=src["enabled"],
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[NewsSource.slug],
            set_={
                "name": stmt.excluded.name,
                "homepage": stmt.excluded.homepage,
                "enabled": stmt.excluded.enabled,
            },
        )
        await session.execute(stmt)
        source_id = (
            await session.execute(select(NewsSource.id).where(NewsSource.slug == src["slug"]))
        ).scalar_one()

        for position, feed in enumerate(src["feeds"]):
            fstmt = pg_insert(NewsFeed).values(
                source_id=source_id,
                url=feed["url"],
                category=feed["category"],
                position=position,
            )
            fstmt = fstmt.on_conflict_do_update(
                index_elements=[NewsFeed.url],
                set_={
                    "source_id": fstmt.excluded.source_id,
                    "category": fstmt.excluded.category,
                    "position": fstmt.excluded.position,
                },
            )
            await session.execute(fstmt)

        # Drop feeds removed from the registry so they stop being fetched.
        urls = [f["url"] for f in src["feeds"]]
        await session.execute(
            delete(NewsFeed).where(NewsFeed.source_id == source_id, NewsFeed.url.notin_(urls))
        )
    await session.commit()
