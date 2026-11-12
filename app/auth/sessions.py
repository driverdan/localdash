"""Server-side login sessions: an opaque random token, stored only as its hash.

The browser holds the raw token in the `localdash_session` cookie; the database
holds `sha256(token)` with the user and a fixed expiry. A session is valid only
while its row exists, its expiry is in the future and its user is active, so
logout, `set-password` and deactivating a user all take effect on the next
request. SHA-256 without a salt is enough: the token is 256 random bits, not a
human-chosen secret.

These functions do not commit; the caller owns the transaction (login commits
the session with any password-hash upgrade, `set-password` commits the new hash
with the revocation).
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Session, User

# 32 random bytes = 256 bits, URL-safe base64 encoded (43 characters).
TOKEN_BYTES = 32


def hash_token(token: str) -> str:
    """The hex SHA-256 of a session token, as stored in `sessions.token_hash`."""
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    lifetime: timedelta,
    now: datetime | None = None,
) -> str:
    """Store a new session for ``user_id`` expiring ``lifetime`` after ``now``.

    Returns the raw token for the cookie; only its hash is stored.
    """
    now = now or datetime.now(UTC)
    token = secrets.token_urlsafe(TOKEN_BYTES)
    db.add(
        Session(
            token_hash=hash_token(token),
            user_id=user_id,
            created_at=now,
            expires_at=now + lifetime,
        )
    )
    await db.flush()
    return token


async def lookup_session(
    db: AsyncSession, token: str, *, now: datetime | None = None
) -> User | None:
    """The active user owning the unexpired session ``token`` names, else None."""
    now = now or datetime.now(UTC)
    return (
        await db.execute(
            select(User)
            .join(Session, Session.user_id == User.id)
            .where(
                Session.token_hash == hash_token(token),
                Session.expires_at > now,
                User.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()


async def delete_session(db: AsyncSession, token: str) -> None:
    """Delete the session ``token`` names, if any."""
    await db.execute(delete(Session).where(Session.token_hash == hash_token(token)))


async def delete_user_sessions(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Delete every session belonging to ``user_id``."""
    await db.execute(delete(Session).where(Session.user_id == user_id))


async def delete_expired_sessions(db: AsyncSession, *, now: datetime | None = None) -> int:
    """Delete sessions whose expiry has passed; returns how many were deleted."""
    now = now or datetime.now(UTC)
    result = cast(
        CursorResult[Any], await db.execute(delete(Session).where(Session.expires_at < now))
    )
    return result.rowcount
