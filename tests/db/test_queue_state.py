"""QUEUE-07 / D-39 / T-02-29 — the last-visit watermark is a DB row, not a cookie.

The properties asserted here are the ones that make "new since I last looked"
trustworthy: a read never writes, the row is created once and only once, and the
boundary can never move backwards (which would resurrect old listings as new).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import QueueState
from app.db.repositories.state_repo import advance_watermark, get_watermark, mark_all_seen

EARLY = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
LATE = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)


def _naive(value: datetime) -> datetime:
    """SQLite stores and returns naive datetimes; compare on the instant."""
    return value.replace(tzinfo=None) if value.tzinfo else value


async def _rows(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(QueueState)) or 0


async def test_a_fresh_database_has_no_watermark_and_a_read_does_not_create_one(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        assert await get_watermark(session) is None
        await session.commit()

    assert await _rows(session_factory) == 0, "a read must never write"


async def test_advance_creates_the_row_once_and_is_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first = await advance_watermark(session, now=EARLY)
        await session.commit()
    assert first == EARLY

    async with session_factory() as session:
        second = await advance_watermark(session, now=LATE)
        await session.commit()
    assert second == LATE

    assert await _rows(session_factory) == 1, "the table is single-row"

    async with session_factory() as session:
        assert await get_watermark(session) == LATE.replace(tzinfo=None)


async def test_an_earlier_now_never_moves_the_watermark_backwards(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A clock skew must not resurrect old listings as new."""
    async with session_factory() as session:
        await advance_watermark(session, now=LATE)
        await session.commit()

    async with session_factory() as session:
        effective = await advance_watermark(session, now=LATE - timedelta(days=1))
        await session.commit()

    assert _naive(effective) == _naive(LATE), "the stored value is kept and returned"
    async with session_factory() as session:
        assert await get_watermark(session) == LATE.replace(tzinfo=None)


async def test_a_null_watermark_always_advances(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """`NULL` means "never viewed" — so even an early `now` is an advance."""
    async with session_factory() as session:
        session.add(QueueState(last_queue_view_at=None, updated_at=EARLY))
        await session.commit()

    async with session_factory() as session:
        assert await get_watermark(session) is None

    async with session_factory() as session:
        effective = await advance_watermark(session, now=EARLY)
        await session.commit()

    assert effective == EARLY


async def test_mark_all_seen_returns_and_stores_the_new_value(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        returned = await mark_all_seen(session, now=LATE)
        await session.commit()

    assert returned == LATE
    async with session_factory() as session:
        assert await get_watermark(session) == LATE.replace(tzinfo=None)
    assert await _rows(session_factory) == 1
