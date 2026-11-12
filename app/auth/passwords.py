"""Password hashing: a thin async wrapper around pwdlib's argon2 hasher.

argon2 is deliberately slow (tens of milliseconds of CPU), so every call runs in
a worker thread and never blocks the event loop that also runs the poll jobs and
the WebSocket. Plaintext passwords are never stored, logged or returned.
"""

from __future__ import annotations

import asyncio
from functools import cache

from pwdlib import PasswordHash

# argon2id with pwdlib's recommended (argon2-cffi default) parameters. A stored
# hash made with other parameters still verifies, and verify_and_update hands
# back a replacement made with these.
_password_hash = PasswordHash.recommended()

# Verified against on the unknown-email login path, so that path costs the same
# argon2 work as a wrong password and its timing does not reveal whether the
# email has an account. Nothing can log in with it: no user row holds it.
_DUMMY_PASSWORD = "localdash-dummy-password-for-timing"


@cache
def _dummy_hash() -> str:
    """A fixed hash made with the current parameters, computed once per process."""
    return _password_hash.hash(_DUMMY_PASSWORD)


async def hash_password(password: str) -> str:
    """The argon2 hash to store for ``password``."""
    return await asyncio.to_thread(_password_hash.hash, password)


async def verify_and_update(password: str, hashed: str) -> tuple[bool, str | None]:
    """Check ``password`` against a stored hash.

    Returns ``(matches, new_hash)``; ``new_hash`` is a fresh hash to store when
    the password matched and the stored hash uses outdated parameters, else None.
    """
    return await asyncio.to_thread(_password_hash.verify_and_update, password, hashed)


def _verify_dummy(password: str) -> None:
    _password_hash.verify(password, _dummy_hash())


async def dummy_verify(password: str) -> None:
    """Spend one argon2 verification on nothing (the unknown-email login path)."""
    await asyncio.to_thread(_verify_dummy, password)
