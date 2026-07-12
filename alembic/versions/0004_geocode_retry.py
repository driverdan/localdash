"""geocode_cache.last_attempted_at for the failure retry pass

Backfilled from created_at so failure rows cached before this migration are
immediately eligible for retry. Kept as raw SQL to match the project's
migration convention.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE geocode_cache
        ADD COLUMN last_attempted_at TIMESTAMPTZ NOT NULL DEFAULT now()
        """
    )
    op.execute("UPDATE geocode_cache SET last_attempted_at = created_at")


def downgrade() -> None:
    op.execute("ALTER TABLE geocode_cache DROP COLUMN IF EXISTS last_attempted_at")
