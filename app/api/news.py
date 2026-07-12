"""News feature: clustered local-news stories from RSS feeds.

Mounted at /api/v1/news (see app/main.py).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.news import refresh as news_refresh
from app.news import stories
from app.news.registry import CATEGORIES

router = APIRouter()


@router.get("/stories")
async def get_stories(
    hours: Annotated[int, Query(ge=1)] = 72,
    session: AsyncSession = Depends(get_session),
):
    """Clustered stories in the window, plus the category slug->label map."""
    max_hours = 24 * get_settings().news_story_window_days
    return {
        "categories": CATEGORIES,
        "stories": await stories.get_stories(session, min(hours, max_hours)),
    }


@router.get("/sources")
async def get_sources(session: AsyncSession = Depends(get_session)):
    """One row per feed with health telemetry, for the sources footer."""
    return {"sources": await stories.get_sources(session)}


@router.post("/refresh")
async def refresh():
    """Fetch all feeds and recluster on demand."""
    return await news_refresh.refresh()
