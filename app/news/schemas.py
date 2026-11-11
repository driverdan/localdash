"""Response models, typed rows and the refresh result for the news API (/api/v1/news).

Fields are declared in the order the JSON has always carried them; see
app/contracts.py for the shared base model and the datetime rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.contracts import ApiModel, IsoDateTime


@dataclass(frozen=True, slots=True)
class StoryArticle:
    """One clustered article row, as get_stories() reads it for build_stories()."""

    id: int
    cluster_id: int
    url: str
    title: str
    summary: str
    category: str
    published: datetime
    image_url: str | None
    source_name: str
    source_slug: str


class StorySource(ApiModel):
    """One outlet's link within a story (its earliest report)."""

    source: str
    slug: str
    title: str
    url: str
    published: IsoDateTime


class Story(ApiModel):
    id: int
    title: str
    summary: str
    category: str
    image_url: str | None
    first_published: IsoDateTime
    latest_published: IsoDateTime
    source_count: int
    article_count: int
    sources: list[StorySource]


class StoriesResponse(ApiModel):
    # Category slug -> label, in display order (dicts keep insertion order).
    categories: dict[str, str]
    stories: list[Story]


class NewsSourceStatus(ApiModel):
    """One feed row with its fetch telemetry, for the sources footer."""

    slug: str
    name: str
    homepage: str
    enabled: bool
    category: str
    last_fetch: IsoDateTime | None
    last_status: str | None
    article_count: int


class SourcesResponse(ApiModel):
    sources: list[NewsSourceStatus]


@dataclass(frozen=True, slots=True)
class NewsRefreshResult:
    """One news refresh cycle; the body of POST /api/v1/news/refresh."""

    sources: dict[str, str]  # feed label ("<slug>/<category>") -> fetch status
    clusters: int
