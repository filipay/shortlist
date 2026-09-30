"""The `apply_config` screening-question document — the fresh-install fallback and the write.

The load-bearing properties:

* an ABSENT row returns the code-level `DEFAULT_QUESTIONS` (a fresh install works with
  no seed row and no migration);
* a stored list round-trips in order;
* an explicit empty list is preserved (so "no questions" is expressible), distinct
  from the absent-row fallback;
* the repository never commits (the caller owns the commit).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import ApplyConfig
from app.db.repositories.apply_config_repo import (
    DEFAULT_QUESTIONS,
    SINGLETON_ID,
    read_questions,
    write_questions,
)

NOW = datetime(2026, 9, 30, 10, 0, 0, tzinfo=UTC)


async def test_an_absent_row_returns_the_default_seed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        assert await read_questions(session) == list(DEFAULT_QUESTIONS)


async def test_a_write_then_read_round_trips_in_order(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        stored = await write_questions(
            session,
            ["Why this role?", "Notice period?", "Salary?"],
            now=NOW,
        )
        await session.commit()

    assert stored == ["Why this role?", "Notice period?", "Salary?"]

    async with session_factory() as session:
        assert await read_questions(session) == ["Why this role?", "Notice period?", "Salary?"]


async def test_a_second_write_replaces_the_first(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await write_questions(session, ["A", "B"], now=NOW)
        await session.commit()

    async with session_factory() as session:
        await write_questions(session, ["Only"], now=NOW)
        await session.commit()

    async with session_factory() as session:
        assert await read_questions(session) == ["Only"]
        row = await session.get(ApplyConfig, SINGLETON_ID)
    assert row is not None
    assert len(row.questions_json) == 1, "the singleton is upserted, not duplicated"


async def test_an_empty_write_stores_an_explicit_empty_list(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """`[]` means "no questions" and must NOT fall back to the defaults on read."""
    async with session_factory() as session:
        stored = await write_questions(session, [], now=NOW)
        await session.commit()

    assert stored == []
    async with session_factory() as session:
        assert await read_questions(session) == []


async def test_write_trims_and_drops_blank_questions(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        stored = await write_questions(session, ["  Why?  ", "", "   "], now=NOW)
        await session.commit()

    assert stored == ["Why?"]


async def test_write_never_commits(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as writer:
        await write_questions(writer, ["Uncommitted"], now=NOW)
        # deliberately no commit

    async with session_factory() as session:
        stored = await read_questions(session)
    assert stored == list(DEFAULT_QUESTIONS), "the writer must not commit"


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
