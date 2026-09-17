"""Async engine, SQLite PRAGMAs and the session dependency.

The PRAGMA listener targets ``engine.sync_engine`` (not ``engine``) — that is the
documented target for an async engine, and ``foreign_keys=ON`` is a silent no-op
unless ``autocommit`` is toggled on for the duration of the pragma.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings


def apply_sqlite_pragmas(dbapi_connection, connection_record) -> None:  # noqa: ANN001
    """Apply the four PRAGMAs to every new DBAPI connection (M8).

    The pysqlite driver will not apply ``PRAGMA foreign_keys`` while
    ``autocommit`` is False, so it is toggled for the duration of the pragmas
    when the DBAPI connection exposes it. The aiosqlite adapter does not expose
    ``autocommit``; its ``connect`` event runs before any transaction, so the
    pragmas apply directly (verified against SQLAlchemy 2.0 + aiosqlite).
    """
    autocommit = getattr(dbapi_connection, "autocommit", None)
    if autocommit is not None:
        dbapi_connection.autocommit = True
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
    if autocommit is not None:
        dbapi_connection.autocommit = autocommit


def build_engine(url: str) -> AsyncEngine:
    """Create an async engine with the SQLite PRAGMA and transaction listeners.

    The two transaction listeners are the documented SQLAlchemy recipe for making
    **DDL transactional** on pysqlite. Without them the driver takes transaction
    control: it does not begin one for DDL and implicitly COMMITs before it, so a
    `DROP TRIGGER` inside a session is durable even after `session.rollback()`. The
    guarded reset suspends the `listing_events` append-only trigger for the duration of
    its deletes, so that would let a failed reset leave the append-only invariant
    permanently disabled. Setting ``isolation_level = None`` hands transaction control
    back to SQLAlchemy and the ``begin`` listener issues ``BEGIN`` explicitly; DDL then
    rolls back with the rest of the transaction. It also makes the `SAVEPOINT`s every
    repository write relies on (`session.begin_nested()`) real rather than emulated.
    """
    engine = create_async_engine(url)
    event.listens_for(engine.sync_engine, "connect")(apply_sqlite_pragmas)

    @event.listens_for(engine.sync_engine, "connect")
    def _disable_driver_transactions(dbapi_connection, connection_record):  # noqa: ANN001
        dbapi_connection.isolation_level = None

    @event.listens_for(engine.sync_engine, "begin")
    def _begin_explicitly(connection):  # noqa: ANN001
        connection.exec_driver_sql("BEGIN")

    return engine


engine: AsyncEngine = build_engine(settings.database_url_async)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped session."""
    async with async_session_maker() as session:
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """The factory a *background* task should use.

    A request-scoped session cannot outlive its response, so the run trigger
    schedules the pipeline with a factory rather than the request session. It is
    a dependency (not a module global read) so tests can point it at the temp DB.
    """
    return async_session_maker
