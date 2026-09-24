"""D-115 / D-117 / D-118 — the `cv_artifacts` access contracts.

The load-bearing property is D-118: only an `ok` artifact is selectable for a download,
link or attach query, and the predicate is applied in SQL so a blocked or failed row is
unreachable **even by id**. The history read is the opposite: it must return every row,
including blocked and failed, because a blocked attempt is explained, never hidden.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import CvArtifact, Listing
from app.db.repositories import cv_artifact_repo
from app.db.repositories.cv_artifact_repo import (
    history_for_listing,
    insert_artifact,
    latest_for_listing,
    read_for_download,
)

NOW = datetime(2026, 9, 24, 10, 0, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 24, 10, 0, 5, tzinfo=UTC)


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession], listing_id: int = 1
) -> int:
    """A real `listings` row: `cv_artifacts.listing_id` carries a foreign key to it."""
    async with session_factory() as session:
        listing = Listing(
            canonical_url=f"https://example.com/jobs/{listing_id}",
            title=f"Artifact Role {listing_id}",
            first_seen_at=NOW,
            last_seen_at=NOW,
            content_hash=f"artifact-hash-{listing_id}",
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
        return int((await session.scalar(select(func.count()).select_from(CvArtifact))) or 0)


async def _insert(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    listing_id: int = 1,
    compile_status: str = "ok",
    now: datetime = NOW,
    pdf_path: str | None = "/artifacts/1/cv.pdf",
):
    async with session_factory() as session:
        record = await insert_artifact(
            session,
            listing_id=listing_id,
            base_cv_version_id=None,
            patch_json={"listing_id": listing_id},
            change_log_json=[],
            compile_status=compile_status,
            verification_json={"passed": compile_status == "ok"},
            page_count=1 if compile_status == "ok" else None,
            tex_path="/artifacts/1/cv.tex",
            pdf_path=pdf_path if compile_status == "ok" else None,
            now=now,
        )
        await session.commit()
        return record


# --- the write contract --------------------------------------------------------


async def test_insert_artifact_writes_one_row_and_never_commits(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as writer:
        await insert_artifact(
            writer,
            listing_id=1,
            base_cv_version_id=None,
            patch_json={"listing_id": 1},
            change_log_json=[],
            compile_status="ok",
            verification_json={"passed": True},
            page_count=1,
            now=NOW,
        )
        # deliberately no commit

    assert await _count_all(session_factory) == 0, "the writer must not commit"

    await _insert(session_factory)

    assert await _count_all(session_factory) == 1


async def test_an_invalid_compile_status_raises_before_any_sql(
    session_factory: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    with pytest.raises(ValueError, match="unknown compile_status") as excinfo:
        await insert_artifact(
            db_session,
            listing_id=1,
            base_cv_version_id=None,
            patch_json={"listing_id": 1},
            change_log_json=[],
            compile_status="bogus",
            verification_json={},
            page_count=None,
            now=NOW,
        )

    assert "blocked" in str(excinfo.value)
    assert await _count_all(session_factory) == 0


# --- the ok-only predicate -----------------------------------------------------


async def test_a_newer_blocked_row_is_not_returned_by_the_ok_only_read(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    ok = await _insert(session_factory, compile_status="ok", now=NOW)
    await _insert(session_factory, compile_status="blocked", now=LATER)

    async with session_factory() as session:
        selected = await latest_for_listing(session, 1, ok_only=True)

    assert selected is not None
    assert selected.id == ok.id, "the ok-only read must skip the newer blocked row"


async def test_the_status_read_returns_the_newer_blocked_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _insert(session_factory, compile_status="ok", now=NOW)
    blocked = await _insert(session_factory, compile_status="blocked", now=LATER)

    async with session_factory() as session:
        selected = await latest_for_listing(session, 1, ok_only=False)

    assert selected is not None
    assert selected.id == blocked.id


async def test_read_for_download_excludes_blocked_and_failed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    blocked = await _insert(session_factory, compile_status="blocked")
    failed = await _insert(session_factory, compile_status="failed", now=LATER)

    async with session_factory() as session:
        assert await read_for_download(session, blocked.id, ok_only=True) is None
        assert await read_for_download(session, failed.id, ok_only=True) is None
        # The non-ok read still sees them, which is what proves the predicate did it.
        assert await read_for_download(session, blocked.id, ok_only=False) is not None


async def test_read_for_download_returns_the_ok_record(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    ok = await _insert(session_factory, compile_status="ok")

    async with session_factory() as session:
        record = await read_for_download(session, ok.id, ok_only=True)

    assert record is not None
    assert record.id == ok.id
    assert record.compile_status == "ok"
    assert record.pdf_path == "/artifacts/1/cv.pdf"
    assert record.page_count == 1


async def test_history_returns_all_rows_newest_first(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first = await _insert(session_factory, compile_status="ok", now=NOW)
    second = await _insert(session_factory, compile_status="blocked", now=LATER)

    async with session_factory() as session:
        rows = await history_for_listing(session, 1)

    assert [row.id for row in rows] == [second.id, first.id]
    assert {row.compile_status for row in rows} == {"ok", "blocked"}


def test_the_status_vocabulary_is_the_declared_triple() -> None:
    assert cv_artifact_repo.COMPILE_STATUSES == frozenset({"ok", "failed", "blocked"})


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
