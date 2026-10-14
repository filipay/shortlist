"""Retention pruning — the guard suite (D-163..D-168, RUN-07).

The properties this module pins, all from the plan's `must_haves`:

* the preview and the delete run ONE predicate, so the count shown before
  destruction cannot disagree with the number removed;
* the D-165 guards are the queries' own conditions — an application-linked artifact
  and each listing's newest successful artifact are never selected, whatever the
  threshold;
* sizes come from disk (`stat().st_size`), and a stored path that is missing or that
  resolves outside the artifacts directory contributes zero and is reported, never
  raised (T-08-23);
* a bad category or a non-positive age is refused before any SQL.

Each guard is asserted as a *selection* result, never as a caught exception: a guard
implemented as an error path would surface only at the operator's confirm step.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Application, CvArtifact, Listing
from app.db.repositories import cv_artifact_repo
from app.db.repositories.retention_repo import PrunePreview, delete, preview

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
#: Comfortably older than any threshold used below.
OLD = NOW - timedelta(days=400)


@pytest.fixture
def artifacts_root(tmp_path: Path) -> Path:
    """A per-test artifacts directory, so `stat()` and containment are real."""
    root = tmp_path / "artifacts"
    root.mkdir()
    return root


def _write_file(root: Path, name: str, size: int) -> Path:
    path = root / name
    path.write_bytes(b"x" * size)
    return path


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    index: int = 1,
    last_seen_at: datetime = NOW,
) -> int:
    async with session_factory() as session:
        listing = Listing(
            canonical_url="https://example.com/jobs/" + str(index),
            title="Prune Role " + str(index),
            first_seen_at=NOW,
            last_seen_at=last_seen_at,
            content_hash="prune-hash-" + str(index),
            created_at=NOW,
            updated_at=NOW,
            is_active=True,
        )
        session.add(listing)
        await session.commit()
        return int(listing.id)


async def _insert_artifact(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    listing_id: int,
    created_at: datetime,
    status: str = "ok",
    tex_path: str | None = None,
    pdf_path: str | None = None,
) -> int:
    async with session_factory() as session:
        record = await cv_artifact_repo.insert_artifact(
            session,
            listing_id=listing_id,
            base_cv_version_id=None,
            patch_json={},
            change_log_json=[],
            compile_status=status,
            verification_json={"passed": status == "ok"},
            page_count=1 if status == "ok" else None,
            tex_path=tex_path,
            pdf_path=pdf_path,
            now=created_at,
        )
        await session.commit()
        return record.id


async def _artifact_ids(session_factory: async_sessionmaker[AsyncSession]) -> set[int]:
    async with session_factory() as session:
        return {int(row) for row in (await session.execute(select(CvArtifact.id))).scalars().all()}


# --- the artifact category: one predicate, two statements ---------------------


async def test_an_old_unreferenced_non_newest_artifact_is_previewed_and_deleted(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    listing = await _seed_listing(session_factory)
    newest = await _insert_artifact(session_factory, listing_id=listing, created_at=NOW)
    tex = _write_file(artifacts_root, "old.tex", 10)
    pdf = _write_file(artifacts_root, "old.pdf", 20)
    old = await _insert_artifact(
        session_factory,
        listing_id=listing,
        created_at=OLD,
        tex_path=str(tex),
        pdf_path=str(pdf),
    )

    async with session_factory() as session:
        result = await preview(
            session, category="artifacts", age_days=30, artifacts_root=artifacts_root
        )
        assert isinstance(result, PrunePreview)
        assert result.count == 1
        assert result.noun == "artifact"
        assert result.size_bytes == 30
        assert result.size_display == "30 B"
        count, paths = await delete(session, category="artifacts", age_days=30)
        await session.commit()

    # One predicate, two statements: the preview's count IS the delete's count.
    assert count == result.count
    assert sorted(path.name for path in paths) == ["old.pdf", "old.tex"]
    remaining = await _artifact_ids(session_factory)
    assert int(newest) in remaining
    assert int(old) not in remaining


async def test_the_newest_successful_artifact_is_never_selected(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    """The negative control: the newest survives while an OLDER one is still eligible."""
    listing = await _seed_listing(session_factory)
    newest = await _insert_artifact(session_factory, listing_id=listing, created_at=OLD)
    older = await _insert_artifact(
        session_factory, listing_id=listing, created_at=OLD - timedelta(days=100)
    )

    async with session_factory() as session:
        result = await preview(
            session, category="artifacts", age_days=30, artifacts_root=artifacts_root
        )
        assert result.count == 1
        count, _paths = await delete(session, category="artifacts", age_days=30)
        await session.commit()

    assert count == 1
    remaining = await _artifact_ids(session_factory)
    assert int(newest) in remaining
    assert int(older) not in remaining


async def test_a_listings_only_successful_artifact_survives_an_aggressive_threshold(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    listing = await _seed_listing(session_factory)
    await _insert_artifact(session_factory, listing_id=listing, created_at=OLD)

    async with session_factory() as session:
        result = await preview(
            session, category="artifacts", age_days=1, artifacts_root=artifacts_root
        )

    assert result.count == 0


async def test_an_artifact_referenced_by_an_application_is_never_selected(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    listing = await _seed_listing(session_factory)
    # A newer ok artifact exists, so guard 4 does not hide the target; guard 3 must.
    await _insert_artifact(session_factory, listing_id=listing, created_at=NOW)
    target = await _insert_artifact(session_factory, listing_id=listing, created_at=OLD)

    async with session_factory() as session:
        session.add(
            Application(
                listing_id=listing,
                status="applied",
                cv_artifact_id=target,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await session.commit()

    async with session_factory() as session:
        result = await preview(
            session, category="artifacts", age_days=30, artifacts_root=artifacts_root
        )

    assert result.count == 0


async def test_a_blocked_artifact_is_eligible(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    """Guard 4 guards the newest *successful* artifact — a blocked row is neither."""
    listing = await _seed_listing(session_factory)
    await _insert_artifact(session_factory, listing_id=listing, created_at=NOW)
    blocked = await _insert_artifact(
        session_factory, listing_id=listing, created_at=OLD, status="blocked"
    )

    async with session_factory() as session:
        count, _paths = await delete(session, category="artifacts", age_days=30)
        await session.commit()

    assert count == 1
    assert int(blocked) not in await _artifact_ids(session_factory)


# --- sizes come from disk, and a bad path is reported, never fatal -------------


async def test_a_missing_file_contributes_zero_and_is_reported(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path
) -> None:
    listing = await _seed_listing(session_factory)
    await _insert_artifact(session_factory, listing_id=listing, created_at=NOW)
    gone = artifacts_root / "gone.pdf"
    await _insert_artifact(
        session_factory, listing_id=listing, created_at=OLD, tex_path=None, pdf_path=str(gone)
    )

    async with session_factory() as session:
        result = await preview(
            session, category="artifacts", age_days=30, artifacts_root=artifacts_root
        )

    assert result.count == 1
    assert result.size_bytes == 0
    assert result.missing_files == 1


async def test_a_stored_path_outside_the_artifacts_directory_is_not_measured(
    session_factory: async_sessionmaker[AsyncSession], artifacts_root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_bytes(b"x" * 4096)
    listing = await _seed_listing(session_factory)
    await _insert_artifact(session_factory, listing_id=listing, created_at=NOW)
    await _insert_artifact(session_factory, listing_id=listing, created_at=OLD, pdf_path=str(outside))

    async with session_factory() as session:
        result = await preview(
            session, category="artifacts", age_days=30, artifacts_root=artifacts_root
        )

    assert result.count == 1
    assert result.size_bytes == 0
    assert result.missing_files == 1
    assert outside.read_bytes() == b"x" * 4096


# --- validation happens before any SQL ----------------------------------------


@pytest.mark.parametrize(
    ("category", "age_days"),
    [
        ("nope", 30),
        ("", 30),
        ("artifacts", 0),
        ("artifacts", -1),
        ("artifacts", "abc"),
    ],
)
async def test_a_bad_category_or_non_positive_age_is_refused(
    session_factory: async_sessionmaker[AsyncSession],
    artifacts_root: Path,
    category: str,
    age_days: object,
) -> None:
    async with session_factory() as session:
        with pytest.raises(ValueError):
            await preview(
                session, category=category, age_days=age_days, artifacts_root=artifacts_root
            )
        with pytest.raises(ValueError):
            await delete(session, category=category, age_days=age_days)
