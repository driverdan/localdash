"""Auth: password login, logout and the current user.

Mounted at /api/v1/auth (see app/main.py). There is deliberately no
registration endpoint: accounts are created with `python -m app.auth`.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import passwords
from app.auth.accounts import get_user_by_email
from app.auth.deps import SESSION_COOKIE, current_user, session_cookie
from app.auth.models import User
from app.auth.schemas import UserOut
from app.auth.sessions import create_session, delete_session
from app.config import Settings, get_settings
from app.db import get_session

router = APIRouter()


def _login_failed() -> HTTPException:
    # One response for unknown email, wrong password and inactive account, so a
    # caller cannot tell which it was.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
    )


@router.post(
    "/login",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={401: {"description": "Incorrect email or password"}},
)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Check an email (the form's `username`) and password; on success set the session cookie."""
    user = await get_user_by_email(db, form.username)
    if user is None:
        # Spend the same argon2 work as a wrong password so timing does not
        # reveal whether the email has an account.
        await passwords.dummy_verify(form.password)
        raise _login_failed()
    matches, new_hash = await passwords.verify_and_update(form.password, user.hashed_password)
    if not matches or not user.is_active:
        raise _login_failed()
    if new_hash is not None:
        user.hashed_password = new_hash  # stored hash used outdated parameters
    lifetime = timedelta(days=settings.auth_session_days)
    token = await create_session(db, user.id, lifetime=lifetime)
    await db.commit()

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(lifetime.total_seconds()),
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout(
    token: str | None = Depends(session_cookie),
    db: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    """End the cookie's session (if any) and clear the cookie; always 204."""
    if token:
        await delete_session(db, token)
        await db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/me", response_model=UserOut, responses={401: {"description": "Not signed in"}})
async def me(user: User = Depends(current_user)) -> UserOut:
    """The signed-in user's id, email and admin flag."""
    return UserOut(id=user.id, email=user.email, is_superuser=user.is_superuser)
