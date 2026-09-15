"""T-01-10 / PITFALLS M4 — the FTS5 index is external-content and stays in sync.

Creating the virtual table without its triggers is the silent-divergence failure:
the index looks present, but search misses rows inserted after the migration.
The insert/update/delete round-trip through `MATCH` is the proof that it cannot.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing

QUANTUM_TERM = "Quantum"
ZEPHYR_TERM = "Zephyr"


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def _master(connection: sqlite3.Connection, kind: str, name: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master WHERE type = ? AND name = ?",
        (kind, name),
    ).fetchone()
    assert row is not None, f"missing {kind}: {name}"
    return row


async def _match(session: AsyncSession, term: str) -> list[int]:
    # The term is a BOUND parameter: never string-interpolated into SQL.
    result = await session.execute(
        text("SELECT rowid FROM listing_fts WHERE listing_fts MATCH :term"),
        {"term": term},
    )
    return [row[0] for row in result.all()]


def _listing(title: str) -> Listing:
    now = datetime(2026, 9, 15, tzinfo=UTC)
    return Listing(
        canonical_url="https://example.com/jobs/fts-1",
        title=title,
        company_norm="acme",
        description="Build the thing.",
        first_seen_at=now,
        last_seen_at=now,
        content_hash="fts-content-hash",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def test_listing_fts_is_external_content(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        sql = _master(connection, "table", "listing_fts")["sql"]
    finally:
        connection.close()

    assert "USING fts5" in sql
    assert "content='listings'" in sql
    assert "content_rowid='id'" in sql
    assert "porter unicode61" in sql


def test_all_three_triggers_exist(migrated_db: Path) -> None:
    connection = _connect(migrated_db)
    try:
        for trigger in ("listings_ai", "listings_ad", "listings_au"):
            _master(connection, "trigger", trigger)
    finally:
        connection.close()


async def test_orm_insert_is_searchable(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        listing = _listing(f"{QUANTUM_TERM} Engineer")
        session.add(listing)
        await session.commit()
        listing_id = listing.id

        found = await _match(session, QUANTUM_TERM)

    assert listing_id is not None
    assert found == [listing_id]


async def test_update_and_delete_keep_index_in_sync(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        listing = _listing(f"{QUANTUM_TERM} Engineer")
        session.add(listing)
        await session.commit()
        listing_id = listing.id

        listing.title = f"{ZEPHYR_TERM} Engineer"
        await session.commit()

        assert await _match(session, ZEPHYR_TERM) == [listing_id]
        assert await _match(session, QUANTUM_TERM) == []

        await session.delete(listing)
        await session.commit()

        assert await _match(session, ZEPHYR_TERM) == []


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
