"""P8/M8 — every application connection is configured, and FTS5 is available."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from app.db.session import build_engine


async def test_connection_pragmas_are_applied(migrated_db: Path) -> None:
    engine = build_engine(f"sqlite+aiosqlite:///{migrated_db}")
    try:
        async with engine.connect() as connection:
            journal_mode = (await connection.execute(text("PRAGMA journal_mode"))).scalar()
            foreign_keys = (await connection.execute(text("PRAGMA foreign_keys"))).scalar()
            busy_timeout = (await connection.execute(text("PRAGMA busy_timeout"))).scalar()
    finally:
        await engine.dispose()

    assert str(journal_mode).lower() == "wal"
    assert int(foreign_keys) == 1
    assert int(busy_timeout) == 5000


async def test_sqlite_build_has_fts5(migrated_db: Path) -> None:
    engine = build_engine(f"sqlite+aiosqlite:///{migrated_db}")
    try:
        async with engine.connect() as connection:
            rows = (await connection.execute(text("PRAGMA compile_options"))).all()
    finally:
        await engine.dispose()

    options = {row[0] for row in rows}
    assert any("ENABLE_FTS5" in option for option in options), sorted(options)
