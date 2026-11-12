"""FastAPI access-check dependencies: `current_user` (401) and `require_admin` (403).

The session token arrives in the HttpOnly `localdash_session` cookie, read by
FastAPI's `APIKeyCookie` (which also documents it in OpenAPI). A request with no
cookie does no database lookup.

Guard a route with ``user: User = Depends(current_user)`` (any active signed-in
user) or ``Depends(require_admin)`` (an admin). Mutating routes must not be GETs:
the cookie is `SameSite=Lax`, which is the CSRF protection, and Lax still sends
the cookie on cross-site top-level GET navigations.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyCookie
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.sessions import lookup_session
from app.db import get_session

SESSION_COOKIE = "localdash_session"

session_cookie = APIKeyCookie(name=SESSION_COOKIE, auto_error=False)


async def current_user(
    token: str | None = Depends(session_cookie),
    db: AsyncSession = Depends(get_session),
) -> User:
    """The active user whose unexpired session the cookie names; 401 otherwise."""
    user = await lookup_session(db, token) if token else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def require_admin(user: User = Depends(current_user)) -> User:
    """The signed-in user if they are an admin; 403 for any other signed-in user."""
    if not user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an admin")
    return user
