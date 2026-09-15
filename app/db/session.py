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
    """Create an async engine with the SQLite PRAGMA listener attached."""
    engine = create_async_engine(url)
    event.listens_for(engine.sync_engine, "connect")(apply_sqlite_pragmas)
    return engine


engine: AsyncEngine = build_engine(settings.database_url_async)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped session."""
    async with async_session_maker() as session:
        yield session
