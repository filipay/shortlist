"""Alembic environment.

Alembic runs on the **sync** driver (`sqlite:////data/jobsearch.db`) while the app
runs `sqlite+aiosqlite:////data/jobsearch.db`; both point at the same file. The
URL is read from `app.config.settings` so both surfaces stay in one place.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, event, pool

from alembic import context

# Make `app` importable when Alembic is invoked from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.db.models  # noqa: E402,F401  (registers every table on Base.metadata)
from app.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import apply_sqlite_pragmas  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# `%` is the configparser interpolation character; escape it so a URL carrying a
# percent-encoded character survives `set_main_option`.
config.set_main_option("sqlalchemy.url", settings.database_url_sync.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    # The entrypoint runs `alembic upgrade head` before `exec uvicorn`, so the
    # database file must already be in the D-17 configuration (WAL +
    # synchronous=NORMAL) when the first migration lands — otherwise the
    # untuned rollback journal makes a first boot needlessly slow and the file
    # is not in the mode the app documents.
    event.listens_for(connectable, "connect")(apply_sqlite_pragmas)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
