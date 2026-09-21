"""D-77 — the `cv_versions` revision-log contracts.

A rendered artefact can always name the revision it was built from only if every
accepted revision snapshots its fact payload, a string schema version and a
source from the declared vocabulary, with exactly one row current at a time and a
writer that never commits. These tests pin each of those, plus the guard-can-fail
companions the repo's style requires.
"""

from __future__ import annotations

import sqlite3
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import CvVersion
from app.db.repositories import cv_repo
from app.db.repositories.cv_repo import current_version, snapshot_version

NOW = datetime(2026, 9, 21, 9, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 21, 9, 0, 5, tzinfo=UTC)

PAYLOAD = {"schema_version": 1, "sections": [{"id": "sec.experience"}]}


async def _count_all(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        return int(
            (await session.scalar(select(func.count()).select_from(CvVersion))) or 0
        )


async def _count_current(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        return int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(CvVersion)
                    .where(CvVersion.is_current.is_(True))
                )
            )
            or 0
        )


# --- the write contract --------------------------------------------------------


async def test_snapshot_returns_a_frozen_record(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        record = await snapshot_version(
            session,
            facts_json=PAYLOAD,
            schema_version=1,
            source="hand",
            label="base",
            now=NOW,
        )
        await session.commit()

    assert record.id > 0
    assert record.label == "base"
    assert record.schema_version == "1"
    assert record.source == "hand"
    assert record.is_current is True
    assert record.created_at == NOW

    with pytest.raises(FrozenInstanceError):
        record.label = "mutated"  # type: ignore[misc]


async def test_the_schema_version_is_stored_as_a_string(
    session_factory: async_sessionmaker[AsyncSession], migrated_db: Path
) -> None:
    """Read the RAW column through the driver, not the ORM.

    The ORM would coerce `"1"` and `1` alike, so only the raw read proves the
    stored value is the string the column expects.
    """
    async with session_factory() as session:
        await snapshot_version(
            session, facts_json=PAYLOAD, schema_version=1, source="hand", now=NOW
        )
        await session.commit()

    connection = sqlite3.connect(migrated_db)
    try:
        stored = connection.execute("SELECT schema_version FROM cv_versions").fetchone()
    finally:
        connection.close()

    assert stored is not None
    assert stored[0] == "1"
    assert isinstance(stored[0], str)


async def test_the_writer_never_commits_the_callers_transaction(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as writer:
        await snapshot_version(
            writer, facts_json=PAYLOAD, schema_version=1, source="hand", now=NOW
        )
        # deliberately no commit

    assert await _count_all(session_factory) == 0

    async with session_factory() as writer:
        await snapshot_version(
            writer, facts_json=PAYLOAD, schema_version=1, source="hand", now=NOW
        )
        await writer.commit()

    assert await _count_all(session_factory) == 1


async def test_an_unknown_source_raises_before_any_sql(
    session_factory: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    with pytest.raises(ValueError, match="unknown source") as excinfo:
        await snapshot_version(
            db_session, facts_json=PAYLOAD, schema_version=1, source="bogus"
        )

    assert "import_tex" in str(excinfo.value)
    assert await _count_all(session_factory) == 0


# --- exactly one current row ---------------------------------------------------


async def test_the_first_snapshot_leaves_exactly_one_current_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # The guard cannot pass on a table the test never populated.
    assert await _count_current(session_factory) == 0

    async with session_factory() as session:
        await snapshot_version(
            session, facts_json=PAYLOAD, schema_version=1, source="hand", now=NOW
        )
        await session.commit()

    assert await _count_current(session_factory) == 1


async def test_exactly_one_row_is_current_after_two_snapshots(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first = await snapshot_version(
            session, facts_json=PAYLOAD, schema_version=1, source="hand", now=NOW
        )
        second = await snapshot_version(
            session,
            facts_json=PAYLOAD,
            schema_version=1,
            source="import_tex",
            now=LATER,
        )
        await session.commit()

    assert await _count_current(session_factory) == 1

    async with session_factory() as session:
        current = await current_version(session)

    assert current is not None
    assert current.id == second.id
    assert current.id != first.id


async def test_a_failed_insert_leaves_the_previous_revision_current(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """WR-01: the current-row clear must roll back WITH the failed insert.

    Before the fix the clear ran in the OUTER transaction, ahead of the
    SAVEPOINT, so a failed INSERT committed the clear and left the table with
    ZERO current rows. The payload below is unserialisable, so the INSERT raises
    inside the SAVEPOINT; the previous revision must remain the one current row.
    """
    async with session_factory() as session:
        first = await snapshot_version(
            session, facts_json=PAYLOAD, schema_version=1, source="hand", now=NOW
        )
        await session.commit()

    assert await _count_current(session_factory) == 1

    async with session_factory() as session:
        # `{1, 2}` is not JSON-serialisable, so the flush inside the SAVEPOINT
        # raises. The exception class is SQLAlchemy's to choose; what matters is
        # that it propagates rather than being swallowed.
        with pytest.raises(Exception):
            await snapshot_version(
                session,
                facts_json={"unserialisable": {1, 2}},
                schema_version=1,
                source="hand",
                now=LATER,
            )
        await session.commit()

    assert await _count_all(session_factory) == 1
    assert await _count_current(session_factory) == 1

    async with session_factory() as session:
        current = await current_version(session)

    assert current is not None
    assert current.id == first.id


# --- current_version -----------------------------------------------------------


async def test_current_version_is_none_on_an_empty_table(
    db_session: AsyncSession,
) -> None:
    assert await current_version(db_session) is None


async def test_current_version_breaks_a_same_timestamp_tie_by_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Two rows share a timestamp; the read resolves to the higher id.

    Both rows carry the current flag — the state a crash mid-swap could leave —
    so only the `id` tie-break can make the read deterministic.
    """
    async with session_factory() as session:
        session.add(
            CvVersion(
                label="first",
                schema_version="1",
                source="hand",
                facts_json=PAYLOAD,
                created_at=NOW,
                is_current=True,
            )
        )
        session.add(
            CvVersion(
                label="second",
                schema_version="1",
                source="hand",
                facts_json=PAYLOAD,
                created_at=NOW,
                is_current=True,
            )
        )
        await session.commit()

    async with session_factory() as session:
        current = await current_version(session)

    assert current is not None
    assert current.label == "second"


# --- the payload round-trips ---------------------------------------------------


async def test_the_fact_payload_round_trips_and_is_visible_to_the_callers_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        record = await snapshot_version(
            session,
            facts_json=PAYLOAD,
            schema_version=1,
            source="import_tex",
            now=NOW,
        )
        await session.commit()

        row = await session.get(CvVersion, record.id)

    assert row is not None
    assert row.facts_json == PAYLOAD


def test_the_source_vocabulary_is_the_declared_pair() -> None:
    assert cv_repo.SOURCES == frozenset({"import_tex", "hand"})


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
