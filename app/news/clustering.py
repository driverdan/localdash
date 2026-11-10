"""Group articles that report the same event into stories.

Clusters are recomputed over the story window after every fetch, and each
story is stored as the smallest member article id (news_articles.cluster_id).
The goal is "same event", not "same topic": two crashes on different highways
share plenty of words but are different stories.

How two articles are compared:

* Tokens (title_tokens: words over 2 chars minus stopwords, plus numbers) are
  weighted by rarity, ln((N+1)/(df+1)), with document frequency counted over a
  30-day lookback corpus. A shared "man" or "police" therefore counts for far
  less than a shared "amnicola" or "27". The long lookback keeps weights
  steady between 15-minute refreshes, so borderline pairs don't flicker.
* Titles match on weighted Jaccard, or on weighted containment with a Jaccard
  floor (containment alone over-rewards short titles).
* Vetoes: titles that both carry numbers but share none ("Dist. 23" vs
  "Dist. 24") don't match; neither do articles whose summaries share almost
  nothing; neither do same-outlet titles posted more than 12h apart that are
  identical apart from case, punctuation and plurals (recurring columns such
  as a daily arrest report).

How stories are built: articles are taken in publish order and each joins the
existing story that it matches best, provided that story's first article is no
more than 36h older and the article matches at least half of the story's
members. Requiring a majority (rather than union-find's single link) is what
stops one weak match from chaining two unrelated stories together.

The thresholds were tuned against tests/fixtures/news_clustering.json, a
hand-labeled window of real articles; test_news_clustering.py asserts the
pairwise precision/recall they achieve.

The similarity math lives in pure functions (assign_clusters) so it is
testable offline; recluster() is the async DB wrapper.
"""

from __future__ import annotations

import asyncio
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.news.models import NewsArticle
from app.news.textutil import title_tokens

# An article may join a story only within this many hours of the story's first article.
STORY_WINDOW_HOURS = 36
# Document frequencies for token weights are counted over this many days of articles.
IDF_LOOKBACK_DAYS = 30
# Same outlet + identical title further apart than this = a recurring column, not one story.
RECURRING_TITLE_HOURS = 12
_COLUMN_WORD_RE = re.compile(r"[a-z0-9]+")

# Title match: weighted Jaccard alone, or weighted containment backed by a Jaccard
# floor and a minimum number of shared tokens.
MATCH_JACCARD = 0.35
MATCH_CONTAINMENT = 0.45
CONTAINMENT_JACCARD_FLOOR = 0.30
CONTAINMENT_MIN_SHARED = 2
# Summary veto: when both articles have a summary of at least MIN_SUMMARY_CHARS,
# their title+summary weighted Jaccard must reach SUMMARY_VETO.
SUMMARY_VETO = 0.12
MIN_SUMMARY_CHARS = 40


@dataclass(frozen=True)
class ClusterArticle:
    """The article fields clustering needs."""

    id: int
    source_id: int
    published: datetime
    title: str
    summary: str = ""


@dataclass(frozen=True)
class _Prepared:
    id: int
    source_id: int
    ts: float
    norm_title: str
    title_toks: frozenset
    numbers: frozenset
    # Title+summary tokens; None when the article has no usable summary.
    text_toks: frozenset | None


class _Weights:
    """IDF weights from a corpus; tokens absent from the corpus get the maximum weight."""

    def __init__(self, docs: list[frozenset]):
        df: dict[str, int] = {}
        for doc in docs:
            for tok in doc:
                df[tok] = df.get(tok, 0) + 1
        n = len(docs)
        self._idf = {tok: math.log((n + 1) / (count + 1)) for tok, count in df.items()}
        self._max = math.log(n + 1)

    def total(self, toks: Iterable[str]) -> float:
        return sum(self._idf.get(tok, self._max) for tok in toks)


def build_weights(corpus: Iterable[tuple[str, str]]) -> tuple[_Weights, _Weights]:
    """Return (title weights, title+summary weights) from (title, summary) pairs."""
    title_docs, text_docs = [], []
    for title, summary in corpus:
        title_docs.append(title_tokens(title))
        text_docs.append(title_tokens(f"{title} {summary or ''}"))
    return _Weights(title_docs), _Weights(text_docs)


def weighted_jaccard(a: frozenset, b: frozenset, weights: _Weights) -> float:
    union = weights.total(a | b)
    return weights.total(a & b) / union if union else 0.0


def weighted_containment(a: frozenset, b: frozenset, weights: _Weights) -> float:
    smaller = min(weights.total(a), weights.total(b))
    return weights.total(a & b) / smaller if smaller else 0.0


def _is_year(tok: str) -> bool:
    return len(tok) == 4 and tok[:2] in ("19", "20")


def _column_key(title: str) -> str:
    """Title normalized for the recurring-column check.

    Case, punctuation and a trailing plural "s" are ignored, so "Latest Hamilton
    County Arrest Report" and "... Arrest Reports" count as the same column.
    """
    words = _COLUMN_WORD_RE.findall(title.lower())
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


def _prepare(article: ClusterArticle) -> _Prepared:
    toks = title_tokens(article.title)
    summary = article.summary or ""
    return _Prepared(
        id=article.id,
        source_id=article.source_id,
        ts=article.published.timestamp(),
        norm_title=_column_key(article.title),
        title_toks=toks,
        numbers=frozenset(t for t in toks if t.isdigit() and not _is_year(t)),
        text_toks=(
            title_tokens(f"{article.title} {summary}")
            if len(summary) >= MIN_SUMMARY_CHARS
            else None
        ),
    )


def _matches(a: _Prepared, b: _Prepared, title_w: _Weights, text_w: _Weights) -> bool:
    """True when a and b look like reports of the same event."""
    if (
        a.source_id == b.source_id
        and a.norm_title == b.norm_title
        and abs(a.ts - b.ts) > RECURRING_TITLE_HOURS * 3600
    ):
        return False
    if a.numbers and b.numbers and not (a.numbers & b.numbers):
        return False

    jaccard = weighted_jaccard(a.title_toks, b.title_toks, title_w)
    if jaccard < MATCH_JACCARD and (
        jaccard < CONTAINMENT_JACCARD_FLOOR
        or len(a.title_toks & b.title_toks) < CONTAINMENT_MIN_SHARED
        or weighted_containment(a.title_toks, b.title_toks, title_w) < MATCH_CONTAINMENT
    ):
        return False

    # Collapsing this would turn the tail into a negated boolean return (SIM103).
    if a.text_toks is not None and b.text_toks is not None:  # noqa: SIM102
        if weighted_jaccard(a.text_toks, b.text_toks, text_w) < SUMMARY_VETO:
            return False
    return True


def assign_clusters(
    articles: Sequence[ClusterArticle],
    corpus: Iterable[tuple[str, str]] | None = None,
) -> dict[int, int]:
    """Pure clustering: articles -> {article_id: cluster_id (smallest member id)}.

    corpus is the (title, summary) pairs used to weight tokens; it defaults to the
    articles themselves. The result does not depend on the order of either input.
    """
    if corpus is None:
        corpus = [(a.title, a.summary) for a in articles]
    title_w, text_w = build_weights(corpus)
    items = sorted((_prepare(a) for a in articles), key=lambda p: (p.ts, p.id))
    window = STORY_WINDOW_HOURS * 3600

    # Stories are created in publish order, so their anchors (first-article
    # times) never decrease and expired stories form a prefix we can skip.
    anchors: list[float] = []
    members: list[list[_Prepared]] = []
    first_open = 0
    for item in items:
        while first_open < len(anchors) and item.ts - anchors[first_open] > window:
            first_open += 1
        best: tuple[float, float, int] | None = None
        best_idx = -1
        for idx in range(first_open, len(anchors)):
            group = members[idx]
            hits = sum(_matches(item, m, title_w, text_w) for m in group)
            if hits == 0 or 2 * hits < len(group):
                continue
            # Highest match fraction; ties go to the earlier story, then the smaller id.
            key = (hits / len(group), -anchors[idx], -min(m.id for m in group))
            if best is None or key > best:
                best, best_idx = key, idx
        if best_idx >= 0:
            members[best_idx].append(item)
        else:
            anchors.append(item.ts)
            members.append([item])

    clusters: dict[int, int] = {}
    for group in members:
        cluster_id = min(m.id for m in group)
        for m in group:
            clusters[m.id] = cluster_id
    return clusters


async def recluster(session: AsyncSession, *, window_days: int, now: datetime | None = None) -> int:
    """Assign cluster_id to all articles in the story window. Returns cluster count.

    The window is the ``window_days`` days before ``now`` (default: the
    current UTC time, read once).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    corpus_cutoff = now - timedelta(days=max(IDF_LOOKBACK_DAYS, window_days))
    rows = (
        await session.execute(
            select(
                NewsArticle.id,
                NewsArticle.source_id,
                NewsArticle.published,
                NewsArticle.title,
                NewsArticle.summary,
            ).where(NewsArticle.published >= corpus_cutoff)
        )
    ).all()
    articles = [
        ClusterArticle(r.id, r.source_id, r.published, r.title, r.summary or "")
        for r in rows
        if r.published >= cutoff
    ]
    if not articles:
        return 0
    corpus = [(r.title, r.summary or "") for r in rows]

    # Compares each article with the open stories' members; off the event loop.
    clusters = await asyncio.to_thread(assign_clusters, articles, corpus)

    await session.execute(
        update(NewsArticle),
        [{"id": aid, "cluster_id": cid} for aid, cid in clusters.items()],
    )
    await session.commit()
    return len(set(clusters.values()))
