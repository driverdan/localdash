"""One scheduled weather refresh: force the cache, ping clients on change.

The weather cache is otherwise lazy (refreshed on request), so without this
cycle a client waiting for a ping before refetching would never hear anything.

The change check compares against the payload the previous *scheduled* refresh
produced (`_last_payload`), not against whatever is in the cache. A
request-driven refresh can update the cache between ticks without pinging; by
comparing against the last scheduled payload, the next tick still tells clients
about that change.

Failures propagate (as news and events do), so the scheduler's shared wrapper
logs them. The comparison only runs after a successful fetch, so a failed
refresh never pings and leaves `_last_payload` untouched.
"""

from __future__ import annotations

import logging

from app.weather.schemas import WeatherPayload
from app.weather.service import service
from app.ws import manager

log = logging.getLogger(__name__)

# Last payload a scheduled refresh produced; pings fire only when it changes.
_last_payload: WeatherPayload | None = None


async def refresh() -> None:
    """Force a weather cache refresh; ping `weather` when the payload changed."""
    global _last_payload
    payload = await service.get_current(force=True)
    if payload != _last_payload:
        _last_payload = payload
        await manager.ping("weather")
