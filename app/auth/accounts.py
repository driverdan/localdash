"""User accounts: email normalisation, lookup, creation and password changes.

Accounts are created by an operator (`python -m app.auth`), never over HTTP.
Emails are normalised with ``strip().lower()`` before they are stored or
compared; the `users` table CHECKs the stored value is lowercase.

Like sessions.py, these functions do not commit; the caller owns the
transaction.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.passwords import hash_password
from app.auth.sessions import delete_user_sessions

MIN_PASSWORD_LENGTH = 12


class AccountError(ValueError):
    """An account operation was refused (duplicate or unknown email, weak password)."""


def normalize_email(email: str) -> str:
    """The stored / compared form of an email: surrounding whitespace removed, lowercase."""
    return email.strip().lower()


def check_password(password: str) -> None:
    """Raise AccountError when ``password`` is too short to accept."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AccountError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """The user with ``email`` (normalised before comparing), else None."""
    return (
        await db.execute(select(User).where(User.email == normalize_email(email)))
    ).scalar_one_or_none()


async def create_user(
    db: AsyncSession, email: str, password: str, *, is_superuser: bool = False
) -> User:
    """Add an active user; raises AccountError on a duplicate email or short password."""
    check_password(password)
    email = normalize_email(email)
    if await get_user_by_email(db, email) is not None:
        raise AccountError(f"a user with email {email!r} already exists")
    user = User(
        email=email,
        hashed_password=await hash_password(password),
        is_active=True,
        is_superuser=is_superuser,
    )
    db.add(user)
    await db.flush()
    return user


async def set_password(db: AsyncSession, email: str, password: str) -> User:
    """Replace a user's password and revoke all their sessions.

    Raises AccountError on an unknown email or short password.
    """
    check_password(password)
    user = await get_user_by_email(db, email)
    if user is None:
        raise AccountError(f"no user with email {normalize_email(email)!r}")
    user.hashed_password = await hash_password(password)
    await delete_user_sessions(db, user.id)
    await db.flush()
    return user
