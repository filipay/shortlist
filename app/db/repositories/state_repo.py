"""Queue-state repository — the single-row "last visit" watermark (D-39 / QUEUE-07).

`queue_state.last_queue_view_at` is NULLABLE on purpose: `NULL` means "never viewed",
so every listing is new until the queue is first opened. There is deliberately no
cookie — the watermark lives in a **database row**, so "what is new since I last
looked" survives a restart, is not client-controlled, and is auditable (T-02-29).

Exactly two things write it: opening the queue page (`GET /`) and the explicit
`Mark all as seen` action. No other read advances it — that is why plan 02-05 read
the watermark without touching it, and why `GET /queue/list` (a fragment swap) does
not either. Every function here takes the session first, never commits, and flushes;
the caller owns the commit.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import QueueState


def _naive(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; normalise both sides of a comparison.

    Without this, a tz-aware `now` from the route compared against a naive stored
    value raises `TypeError` — the same hazard plan 02-05 handled the same way.
    """
    if value is None:
        return None
    return value.replace(tzinfo=None) if value.tzinfo else value


async def _load(session: AsyncSession) -> QueueState | None:
    return (
        (await session.execute(select(QueueState).order_by(QueueState.id).limit(1)))
        .scalars()
        .first()
    )


async def get_watermark(session: AsyncSession) -> datetime | None:
    """The stored watermark, or `None` when the queue has never been viewed.

    Never creates the row: a read must not have a side effect, and "no row" and
    "row with NULL" mean the same thing to every caller — everything is new.
    """
    row = await _load(session)
    return row.last_queue_view_at if row is not None else None


async def advance_watermark(session: AsyncSession, *, now: datetime) -> datetime:
    """Move the watermark to `now` and return the effective value.

    **Never moves backwards.** A `now` earlier than the stored value is ignored and
    the stored value is returned: a clock skew or an out-of-order request must not
    resurrect old listings as new, or "new since last visit" would become
    unfalsifiable. `NULL` (never viewed) always advances.

    The single row is created if it does not exist, SAVEPOINT-wrapped as
    `source_repo.ensure_registered_sources` does, so a racing insert degrades to a
    re-read rather than an exception.
    """
    row = await _load(session)
    if row is None:
        try:
            async with session.begin_nested():
                row = QueueState(last_queue_view_at=now, updated_at=now)
                session.add(row)
                await session.flush()
        except IntegrityError:  # a concurrent writer won the race; re-read instead
            row = await _load(session)
            if row is None:  # pragma: no cover — the row exists, we just lost the race
                raise
        return row.last_queue_view_at

    stored = row.last_queue_view_at
    if stored is None or (_naive(now) or now) > (_naive(stored) or stored):
        row.last_queue_view_at = now
        row.updated_at = now
        await session.flush()
        return now
    return stored


async def mark_all_seen(session: AsyncSession, *, now: datetime) -> datetime:
    """The explicit `Mark all as seen` action.

    Deliberately its own name rather than a bare call to `advance_watermark`: the
    route and the test then state the INTENT, and the two call sites can diverge
    later without one silently changing the other's meaning.
    """
    return await advance_watermark(session, now=now)


__all__ = ["advance_watermark", "get_watermark", "mark_all_seen"]
