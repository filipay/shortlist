"""QUEUE-02 — the two-key Tier-1 upsert is idempotent, including the NULL id case."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import ListingSource, Source
from app.db.repositories import listing_repo
from app.db.repositories.listing_repo import UpsertOutcome, upsert_listing_source

CANONICAL_URL = "https://example.com/jobs/1"


def _norm(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "canonical_url": CANONICAL_URL,
        "source_listing_id": "abc123",
        "source_url": "https://example.com/jobs/1?utm_source=linkedin",
        "canonical_source_url": CANONICAL_URL,
        "title": "Senior Python Engineer",
        "company_norm": "acme",
        "location_raw": "Dublin, Ireland",
        "description": "Build the thing.",
        "content_hash": "content-hash-1",
        "raw_hash": "raw-hash-1",
    }
    base.update(overrides)
    return base


async def _register_source(
    session_factory: async_sessionmaker[AsyncSession], name: str = "linkedin"
) -> None:
    async with session_factory() as session:
        session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _count_listing_sources(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(ListingSource)) or 0


async def test_same_source_listing_id_upserts_one_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_source(session_factory)
    first_seen = datetime(2026, 9, 1, tzinfo=UTC)
    second_seen = first_seen + timedelta(days=1)

    async with session_factory() as session:
        created = await upsert_listing_source(
            session, source="linkedin", norm=_norm(), run_id=None, now=first_seen
        )
        await session.commit()

    async with session_factory() as session:
        updated = await upsert_listing_source(
            session, source="linkedin", norm=_norm(), run_id=None, now=second_seen
        )
        await session.commit()
        row = (
            await session.execute(select(ListingSource))
        ).scalar_one()
        count = await _count_listing_sources(session)

    assert created.kind == "created"
    assert updated.kind == "updated"
    assert count == 1
    # SQLite DATETIME round-trips as naive UTC.
    assert row.last_seen_at == second_seen.replace(tzinfo=None)


async def test_different_source_listing_ids_share_one_row_via_key_b(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Key B: same canonical URL under a different non-null id collapses to one row."""
    await _register_source(session_factory)

    async with session_factory() as session:
        await upsert_listing_source(
            session,
            source="linkedin",
            norm=_norm(source_listing_id="first-id"),
            run_id=None,
            now=datetime(2026, 9, 1, tzinfo=UTC),
        )
        await session.commit()

    async with session_factory() as session:
        outcome = await upsert_listing_source(
            session,
            source="linkedin",
            norm=_norm(source_listing_id="second-id"),
            run_id=None,
            now=datetime(2026, 9, 2, tzinfo=UTC),
        )
        await session.commit()
        count = await _count_listing_sources(session)

    assert outcome.kind == "updated"
    assert count == 1


async def test_two_null_source_listing_ids_upsert_one_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The mandatory case: SQLite treats NULLs as distinct, so a single
    (source, source_listing_id) unique index would insert a duplicate every run.
    """
    await _register_source(session_factory)

    async with session_factory() as session:
        created = await upsert_listing_source(
            session,
            source="linkedin",
            norm=_norm(source_listing_id=None),
            run_id=None,
            now=datetime(2026, 9, 1, tzinfo=UTC),
        )
        await session.commit()

    async with session_factory() as session:
        updated = await upsert_listing_source(
            session,
            source="linkedin",
            norm=_norm(source_listing_id=None),
            run_id=None,
            now=datetime(2026, 9, 2, tzinfo=UTC),
        )
        await session.commit()
        count = await _count_listing_sources(session)

    assert created.kind == "created"
    assert updated.kind == "updated"
    assert count == 1


async def test_concurrent_insert_race_is_caught_and_resolved(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An IntegrityError from a concurrent inserter is caught inside the
    SAVEPOINT, re-SELECTed, and reported as `updated` with one row."""
    await _register_source(session_factory)

    async with session_factory() as session:
        await upsert_listing_source(
            session,
            source="linkedin",
            norm=_norm(),
            run_id=None,
            now=datetime(2026, 9, 1, tzinfo=UTC),
        )
        await session.commit()

    real_find = listing_repo._find_by_keys
    calls = {"n": 0}

    async def _miss_once(
        session: AsyncSession,
        *,
        source: str,
        source_listing_id: str | None,
        canonical_source_url: str,
    ) -> ListingSource | None:
        calls["n"] += 1
        if calls["n"] == 1:
            # Simulate "the winner row was not visible at lookup time".
            return None
        return await real_find(
            session,
            source=source,
            source_listing_id=source_listing_id,
            canonical_source_url=canonical_source_url,
        )

    monkeypatch.setattr(listing_repo, "_find_by_keys", _miss_once)

    async with session_factory() as session:
        outcome = await upsert_listing_source(
            session,
            source="linkedin",
            norm=_norm(),
            run_id=None,
            now=datetime(2026, 9, 2, tzinfo=UTC),
        )
        await session.commit()
        count = await _count_listing_sources(session)

    assert isinstance(outcome, UpsertOutcome)
    assert outcome.kind == "updated"
    assert count == 1
    assert calls["n"] >= 2
