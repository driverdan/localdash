"""auth: users and sessions

User accounts (email + argon2 hash, active and admin flags) and server-side
sessions keyed by the SHA-256 hash of the cookie token. Plain relational
tables, kept as raw SQL to match the project's migration convention.
`gen_random_uuid()` is built into Postgres 13+.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email           TEXT NOT NULL UNIQUE,
            hashed_password TEXT NOT NULL,
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            is_superuser    BOOLEAN NOT NULL DEFAULT FALSE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_users_email_lowercase CHECK (email = lower(email))
        )
        """
    )

    op.execute(
        """
        CREATE TABLE sessions (
            token_hash TEXT PRIMARY KEY,
            user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_sessions_expires_at ON sessions (expires_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sessions")
    op.execute("DROP TABLE IF EXISTS users")
