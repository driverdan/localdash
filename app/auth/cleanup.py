"""The scheduled expired-session sweep (hourly; see app/scheduler.py).

Expired sessions are already rejected by the lookup, so this only bounds the
`sessions` table's growth. It opens its own session, like the refresh cycles.
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.auth.sessions import delete_expired_sessions
from app.db import SessionLocal

log = logging.getLogger(__name__)


async def cleanup_sessions(*, now: datetime | None = None) -> int:
    """Delete every session whose expiry has passed; returns how many were deleted."""
    async with SessionLocal() as db:
        deleted = await delete_expired_sessions(db, now=now)
        await db.commit()
    if deleted:
        log.info("deleted %d expired sessions", deleted)
    return deleted
