"""Alembic environment — runs migrations with a synchronous psycopg engine,
using the database URL from app settings.

Migrations are hand-written raw SQL, so autogenerate never writes them;
`target_metadata` is here so `alembic check` can verify that the ORM models and
the migrated schema agree (CI runs it right after `alembic upgrade head`).
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

# Feature models register on the shared Base only when imported; without these
# their tables would look like drift to `alembic check`.
import app.events.models  # noqa: F401
import app.news.models  # noqa: F401
from alembic import context
from app.config import get_settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url_sync)
target_metadata = Base.metadata

# Objects the extensions create and own, which no migration or model declares:
# PostGIS's spatial_ref_sys table, and the default time index create_hypertable()
# adds to each hypertable.
EXTENSION_TABLES = {"spatial_ref_sys"}
EXTENSION_INDEXES = {"observations_observed_at_idx"}


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    if type_ == "table" and name in EXTENSION_TABLES:
        return False
    if type_ == "index" and reflected and compare_to is None and name in EXTENSION_INDEXES:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
