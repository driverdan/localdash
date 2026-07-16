"""events: feed-supplied image_url

Additive nullable column; existing rows stay null until re-reported by a
refresh cycle. Raw SQL to match the project's migration convention.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-16
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE events ADD COLUMN image_url TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE events DROP COLUMN IF EXISTS image_url")
