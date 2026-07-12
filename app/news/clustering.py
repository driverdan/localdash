"""Group articles from different outlets that cover the same story.

Ported from ChattNews. Clusters are recomputed over the recent window after
every fetch: articles whose titles are sufficiently similar are merged via
union-find, and each group is stored as the smallest member article id.

Titles from different outlets word the same story very differently, so raw
token overlap alone is unreliable. We weight tokens by rarity across the
current window: sharing several *distinctive* tokens (e.g. "amnicola",
"incline", "hixson") indicates the same story, while ubiquitous local tokens
("chattanooga", "hamilton", "police") carry no signal.

The similarity math lives in pure functions (assign_clusters) so it is
testable offline; recluster() is the async DB wrapper.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.news.models import NewsArticle
from app.news.textutil import title_tokens

JACCARD_THRESHOLD = 0.5
CONTAINMENT_THRESHOLD = 0.8
MIN_SHARED_TOKENS = 3
MIN_SHARED_DISTINCTIVE = 3
SEQ_RATIO_THRESHOLD = 0.85
# A token is "common" (no signal) if it appears in more than this share of titles.
COMMON_DF_RATIO = 0.05
COMMON_DF_MIN = 4


def _same_story(a: dict, b: dict, common_tokens: set) -> bool:
    shared = a["tokens"] & b["tokens"]
    if len(shared) >= MIN_SHARED_TOKENS:
        union = len(a["tokens"] | b["tokens"])
        smaller = min(len(a["tokens"]), len(b["tokens"]))
        if len(shared) / union >= JACCARD_THRESHOLD:
            return True
        if smaller and len(shared) / smaller >= CONTAINMENT_THRESHOLD:
            return True
        # The looser distinctive-overlap rule only applies across outlets:
        # within one outlet it wrongly merges formulaic series headlines
        # (e.g. per-candidate election profiles that share most words).
        if a["source_id"] != b["source_id"] and (
            len(shared - common_tokens) >= MIN_SHARED_DISTINCTIVE
        ):
            return True
    return SequenceMatcher(
        None, a["title"].lower(), b["title"].lower()
    ).ratio() >= SEQ_RATIO_THRESHOLD


def assign_clusters(rows: list[tuple[int, int, str]]) -> dict[int, int]:
    """Pure clustering: (id, source_id, title) rows -> {article_id: cluster_id}.

    cluster_id is the smallest member article id.
    """
    items = [
        {
            "id": aid,
            "source_id": source_id,
            "title": title,
            "tokens": title_tokens(title),
        }
        for aid, source_id, title in rows
    ]

    df: dict[str, int] = {}
    for item in items:
        for tok in item["tokens"]:
            df[tok] = df.get(tok, 0) + 1
    df_limit = max(COMMON_DF_MIN, len(items) * COMMON_DF_RATIO)
    common_tokens = {tok for tok, n in df.items() if n > df_limit}

    parent = {item["id"]: item["id"] for item in items}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if find(a["id"]) == find(b["id"]):
                continue
            if _same_story(a, b, common_tokens):
                union(a["id"], b["id"])

    return {item["id"]: find(item["id"]) for item in items}


async def recluster(session: AsyncSession) -> int:
    """Assign cluster_id to all articles in the story window. Returns cluster count."""
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=get_settings().news_story_window_days
    )
    rows = (
        await session.execute(
            select(NewsArticle.id, NewsArticle.source_id, NewsArticle.title)
            .where(NewsArticle.published >= cutoff)
            .order_by(NewsArticle.id)
        )
    ).all()
    if not rows:
        return 0

    # O(n²) pairwise comparison — off the event loop.
    clusters = await asyncio.to_thread(assign_clusters, [tuple(r) for r in rows])

    await session.execute(
        update(NewsArticle),
        [{"id": aid, "cluster_id": cid} for aid, cid in clusters.items()],
    )
    await session.commit()
    return len(set(clusters.values()))
