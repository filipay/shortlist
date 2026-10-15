"""The `cv_drafts` write/read path — one live draft per listing.

The load-bearing property is "one row per listing": a regenerate replaces, it never
accumulates, and the UNIQUE constraint backs the same invariant in the schema. The
repository never commits — the caller owns the commit — so a write is invisible until
the caller commits.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import CvDraft, Listing
from app.db.repositories.cv_draft_repo import (
    CvDraftRecord,
    delete_draft,
    read_draft,
    upsert_draft,
)

NOW = datetime(2026, 9, 28, 10, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 28, 10, 0, 5, tzinfo=UTC)


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession], listing_id: int = 1
) -> int:
    """A real `listings` row: `cv_drafts.listing_id` carries a foreign key to it."""
    async with session_factory() as session:
        listing = Listing(
            canonical_url=f"https://example.com/jobs/{listing_id}",
            title=f"Draft Role {listing_id}",
            first_seen_at=NOW,
            last_seen_at=NOW,
            content_hash=f"draft-hash-{listing_id}",
            created_at=NOW,
            updated_at=NOW,
            is_active=True,
        )
        session.add(listing)
        await session.commit()
        return int(listing.id)


@pytest_asyncio.fixture(autouse=True)
async def _seeded_listing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_listing(session_factory)


async def _count_all(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        return int((await session.scalar(select(func.count()).select_from(CvDraft))) or 0)


# --- the write contract --------------------------------------------------------


async def test_upsert_read_delete_round_trip(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        written = await upsert_draft(
            session,
            listing_id=1,
            base_cv_version_id=None,
            patch_json={"listing_id": 1, "ops": []},
            fact_store_hash="a" * 64,
            requested_model="saved-X",
            now=NOW,
        )
        await session.commit()

    assert isinstance(written, CvDraftRecord)
    assert written.listing_id == 1
    assert written.patch_json == {"listing_id": 1, "ops": []}
    assert written.fact_store_hash == "a" * 64
    assert written.requested_model == "saved-X"

    async with session_factory() as session:
        read = await read_draft(session, 1)
    assert read is not None
    # SQLite round-trips a DateTime as naive; compare the semantic fields and the
    # wall-clock value, not tz-awareness.
    assert read.listing_id == written.listing_id
    assert read.patch_json == written.patch_json
    assert read.fact_store_hash == written.fact_store_hash
    assert read.requested_model == "saved-X"
    assert read.base_cv_version_id == written.base_cv_version_id
    assert read.created_at.replace(tzinfo=None) == written.created_at.replace(tzinfo=None)

    async with session_factory() as session:
        removed = await delete_draft(session, 1)
        await session.commit()
    assert removed is True

    async with session_factory() as session:
        assert await read_draft(session, 1) is None


async def test_upsert_replaces_and_never_accumulates(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await upsert_draft(
            session,
            listing_id=1,
            base_cv_version_id=None,
            patch_json={"listing_id": 1, "first": True},
            fact_store_hash="a" * 64,
            now=NOW,
        )
        await session.commit()
    async with session_factory() as session:
        second = await upsert_draft(
            session,
            listing_id=1,
            base_cv_version_id=None,
            patch_json={"listing_id": 1, "first": False},
            fact_store_hash="b" * 64,
            now=LATER,
        )
        await session.commit()

    assert await _count_all(session_factory) == 1, "a regenerate replaces the live draft"
    async with session_factory() as session:
        read = await read_draft(session, 1)
    assert read is not None
    assert read.patch_json == second.patch_json == {"listing_id": 1, "first": False}
    assert read.fact_store_hash == "b" * 64


async def test_upsert_never_commits(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as writer:
        await upsert_draft(
            writer,
            listing_id=1,
            base_cv_version_id=None,
            patch_json={"listing_id": 1},
            fact_store_hash=None,
            now=NOW,
        )
        # deliberately no commit

    assert await _count_all(session_factory) == 0, "the writer must not commit"
    async with session_factory() as session:
        assert await read_draft(session, 1) is None


async def test_delete_draft_reports_whether_a_row_was_removed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        assert await delete_draft(session, 999) is False

    async with session_factory() as session:
        await upsert_draft(
            session,
            listing_id=1,
            base_cv_version_id=None,
            patch_json={"listing_id": 1},
            fact_store_hash=None,
            now=NOW,
        )
        await session.commit()

    async with session_factory() as session:
        first = await delete_draft(session, 1)
        await session.commit()
    assert first is True

    async with session_factory() as session:
        assert await delete_draft(session, 1) is False


# --- the read path -------------------------------------------------------------


async def test_read_draft_on_an_empty_table_returns_none(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        assert await read_draft(session, 1) is None


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
