"""generalize entity/observation geometry from Point to arbitrary geometry

Widens entities.last_geom and observations.geom from geometry(Point,4326) to
geometry(Geometry,4326) so area sources (e.g. water advisories) are first-class,
and adds entities.geom_fingerprint for ingest change-detection on non-point geometry.

Existing Point rows are preserved (a Point is a valid generic geometry). GIST
indexes are dropped and recreated because the typmod change would otherwise leave
them tied to the old Point type.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_entities_last_geom")
    op.execute("DROP INDEX IF EXISTS ix_obs_geom")

    op.execute(
        "ALTER TABLE entities ALTER COLUMN last_geom "
        "TYPE geometry(Geometry, 4326) USING last_geom::geometry(Geometry, 4326)"
    )
    op.execute(
        "ALTER TABLE observations ALTER COLUMN geom "
        "TYPE geometry(Geometry, 4326) USING geom::geometry(Geometry, 4326)"
    )

    op.execute("ALTER TABLE entities ADD COLUMN geom_fingerprint TEXT")

    op.execute("CREATE INDEX ix_entities_last_geom ON entities USING gist (last_geom)")
    op.execute("CREATE INDEX ix_obs_geom ON observations USING gist (geom)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_entities_last_geom")
    op.execute("DROP INDEX IF EXISTS ix_obs_geom")

    op.execute("ALTER TABLE entities DROP COLUMN IF EXISTS geom_fingerprint")

    # Narrowing back to Point is only valid while no non-point rows exist.
    op.execute(
        "ALTER TABLE entities ALTER COLUMN last_geom "
        "TYPE geometry(Point, 4326) USING last_geom::geometry(Point, 4326)"
    )
    op.execute(
        "ALTER TABLE observations ALTER COLUMN geom "
        "TYPE geometry(Point, 4326) USING geom::geometry(Point, 4326)"
    )

    op.execute("CREATE INDEX ix_entities_last_geom ON entities USING gist (last_geom)")
    op.execute("CREATE INDEX ix_obs_geom ON observations USING gist (geom)")
