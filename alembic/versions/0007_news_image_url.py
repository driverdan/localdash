"""news_articles: feed-supplied image_url

Additive nullable column; existing rows stay null until re-fetched. Raw SQL to
match the project's migration convention.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE news_articles ADD COLUMN image_url TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE news_articles DROP COLUMN IF EXISTS image_url")
