"""Operator CLI for user accounts: ``python -m app.auth <command>``.

    python -m app.auth create-user --email admin@example.com --admin
    python -m app.auth set-password --email admin@example.com

Under Docker: ``docker compose exec app python -m app.auth create-user ...``.

The password is never a command-line argument (it would land in shell history
and the process list): it is prompted for twice when stdin is a terminal, and
read from the first line of stdin otherwise. It must be at least 12 characters.
`set-password` also ends every session the user has. Exits non-zero on any
refusal, leaving the database unchanged.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from collections.abc import Sequence
from typing import TextIO

from app.auth.accounts import AccountError, check_password, create_user, set_password
from app.db import SessionLocal, engine


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.auth", description="Manage LocalDash user accounts."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-user", help="create an active user account")
    create.add_argument("--email", required=True)
    create.add_argument("--admin", action="store_true", help="make the user an admin")

    reset = commands.add_parser(
        "set-password", help="set a user's password and end all of their sessions"
    )
    reset.add_argument("--email", required=True)
    return parser


def read_password(stdin: TextIO) -> str:
    """The new password: prompted twice on a terminal, else stdin's first line."""
    if stdin.isatty():
        password = getpass.getpass("Password: ")
        if getpass.getpass("Repeat password: ") != password:
            raise AccountError("passwords do not match")
        return password
    return stdin.readline().rstrip("\r\n")


async def run(argv: Sequence[str], stdin: TextIO | None = None) -> int:
    """Run one command (password from ``stdin``, default sys.stdin); returns the exit code."""
    args = _parser().parse_args(argv)
    try:
        password = read_password(stdin or sys.stdin)
        check_password(password)
        async with SessionLocal() as db:
            if args.command == "create-user":
                user = await create_user(db, args.email, password, is_superuser=args.admin)
                message = f"created {'admin' if user.is_superuser else 'user'} {user.email}"
            else:
                user = await set_password(db, args.email, password)
                message = f"password set for {user.email}; all of their sessions ended"
            await db.commit()
    except AccountError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(message)
    return 0


async def _main(argv: Sequence[str]) -> int:
    try:
        return await run(argv)
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(_main(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    sys.exit(main())
