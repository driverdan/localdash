"""event_links unique per listing (source_name + source_url), not per source

An event merged from two duplicate listings of the same source legitimately
carries two URLs from that source; the old per-source constraint made them
clobber each other on every refresh. Kept as raw SQL to match the project's
migration convention.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-13
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE event_links DROP CONSTRAINT uq_event_link_source")
    op.execute(
        """
        ALTER TABLE event_links
        ADD CONSTRAINT uq_event_link_source_url UNIQUE (event_id, source_name, source_url)
        """
    )


def downgrade() -> None:
    # Collapse per-listing rows back to one per (event, source) before the
    # old, stricter constraint can be restored.
    op.execute(
        """
        DELETE FROM event_links a
        USING event_links b
        WHERE a.event_id = b.event_id
          AND a.source_name = b.source_name
          AND a.id > b.id
        """
    )
    op.execute("ALTER TABLE event_links DROP CONSTRAINT uq_event_link_source_url")
    op.execute(
        """
        ALTER TABLE event_links
        ADD CONSTRAINT uq_event_link_source UNIQUE (event_id, source_name)
        """
    )
