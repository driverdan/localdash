"""Events feature: aggregated, de-duplicated area events.

Mounted at /api/v1/events (see app/main.py). Distance filtering runs in SQL
against the PostGIS location (geography casts, so units are meters).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.db import get_session
from app.events import refresh as events_refresh
from app.events.models import Event, Tag
from app.events.schemas import EventItem, EventLink, EventsResponse, Origin, TagsResponse

router = APIRouter()

METERS_PER_MILE = 1609.344


def _event_item(
    event: Event, lat: float | None, lon: float | None, meters: float | None
) -> EventItem:
    return EventItem(
        id=event.id,
        title=event.title,
        description=event.description,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        venue_name=event.venue_name,
        address=event.address,
        image_url=event.image_url,
        latitude=lat,
        longitude=lon,
        tags=sorted(tag.name for tag in event.tags),
        links=[
            EventLink(source_name=link.source_name, source_url=link.source_url)
            for link in event.links
        ],
        distance_miles=round(meters / METERS_PER_MILE, 1) if meters is not None else None,
    )


@router.get("/items", response_model=EventsResponse)
async def items(
    topic: Annotated[
        list[str] | None, Query(description="Filter by one or more topic tags")
    ] = None,
    max_miles: Annotated[
        float | None, Query(ge=0, description="Max distance from the origin")
    ] = None,
    lat: Annotated[float | None, Query(description="Distance origin latitude")] = None,
    lon: Annotated[float | None, Query(description="Distance origin longitude")] = None,
    upcoming: Annotated[bool, Query(description="Only events that have not ended")] = True,
    search: Annotated[str | None, Query(description="Case-insensitive title search")] = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> EventsResponse:
    center = (lat, lon) if lat is not None and lon is not None else settings.center
    origin = cast(func.ST_SetSRID(func.ST_MakePoint(center[1], center[0]), 4326), Geography)
    location = cast(Event.location, Geography)
    meters = func.ST_Distance(location, origin)

    stmt = (
        select(Event, func.ST_Y(Event.location), func.ST_X(Event.location), meters)
        .options(selectinload(Event.tags), selectinload(Event.links))
        .order_by(Event.starts_at)
        .limit(limit)
    )
    if upcoming:
        stmt = stmt.where(
            func.coalesce(Event.ends_at, Event.starts_at) >= datetime.now(timezone.utc)
        )
    if search:
        stmt = stmt.where(Event.title.ilike(f"%{search}%"))
    if topic:
        stmt = stmt.where(Event.tags.any(Tag.name.in_(topic)))
    if max_miles is not None:
        # NULL locations fail the predicate, so unlocated events drop out.
        stmt = stmt.where(func.ST_DWithin(location, origin, max_miles * METERS_PER_MILE))

    rows = (await session.execute(stmt)).all()
    return EventsResponse(
        count=len(rows),
        origin=Origin(lat=center[0], lon=center[1]),
        items=[_event_item(event, y, x, m) for event, y, x, m in rows],
    )


@router.get("/tags", response_model=TagsResponse)
async def tags(session: AsyncSession = Depends(get_session)) -> TagsResponse:
    names = (await session.scalars(select(Tag.name).order_by(Tag.name))).all()
    return TagsResponse(tags=list(names))


@router.post("/refresh")
async def refresh() -> dict:
    """Fetch all configured sources and upsert on demand."""
    return await events_refresh.refresh()
