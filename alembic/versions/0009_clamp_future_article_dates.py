"""news: cap future-dated articles' published at their fetch time

Outlets (Chattanoogan.com especially) sometimes publish feed items with a
future pubDate, which pinned them atop the newest-first stories list. The
fetcher now caps published at fetched_at on insert; this one-time backfill
applies the same cap to rows stored before that. Raw SQL to match the
project's migration convention.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Module-level so the DB tests can run the exact statement against seeded rows
# (the suite migrates an empty database, so upgrade() itself touches nothing).
BACKFILL_SQL = "UPDATE news_articles SET published = fetched_at WHERE published > fetched_at"


def upgrade() -> None:
    op.execute(BACKFILL_SQL)


def downgrade() -> None:
    # No-op: the original future feed dates aren't retained, and restoring
    # them would reintroduce the pinned-at-top bug.
    pass
