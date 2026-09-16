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

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# `%` is the configparser interpolation character; escape it so a URL carrying a
# percent-encoded character survives `set_main_option`.
config.set_main_option("sqlalchemy.url", settings.database_url_sync.replace("%", "%%"))

target_metadata = Base.metadata


def _apply_migration_pragmas(dbapi_connection, connection_record) -> None:  # noqa: ANN001
    """PRAGMAs for the Alembic migration connection.

    Mirrors ``app.db.session.apply_sqlite_pragmas`` except ``foreign_keys`` is
    deliberately OFF. Alembic's SQLite batch path recreates tables
    (CREATE -> COPY -> DROP -> RENAME); the DROP step fails with
    ``foreign_keys=ON`` when a child table holds rows referencing the parent
    (migration 0002's ``ck_runs_reason`` recreates ``runs`` while
    ``listing_events``, ``listing_exclusions``, ``scores``, ``llm_calls`` and
    ``source_request_log`` reference ``runs.id``).

    Precedent: **migrations run with ``foreign_keys=OFF``; do not re-enable it
    in ``env.py`` without first solving batch table re-creation.** Migrations
    are trusted, reviewed DDL; the app's own engine
    (``apply_sqlite_pragmas``) still enforces ``foreign_keys=ON`` at runtime.

    The ``getattr(..., "autocommit", None)`` guard is required because
    aiosqlite exposes no ``autocommit`` attribute, while the sync pysqlite
    driver will not apply ``PRAGMA foreign_keys`` while ``autocommit`` is False.
    """
    autocommit = getattr(dbapi_connection, "autocommit", None)
    if autocommit is not None:
        dbapi_connection.autocommit = True
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=OFF")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
    if autocommit is not None:
        dbapi_connection.autocommit = autocommit


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
    # is not in the mode the app documents. `foreign_keys` stays OFF here (see
    # `_apply_migration_pragmas`).
    event.listens_for(connectable, "connect")(_apply_migration_pragmas)
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
