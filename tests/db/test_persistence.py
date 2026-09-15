"""QUEUE-01 — the queue survives a restart, and the WAL is not load-bearing."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Listing, Source
from app.db.repositories.listing_repo import upsert_listing_source
from app.db.session import build_engine

CANONICAL_URL = "https://example.com/jobs/persisted"


def _norm() -> dict[str, object]:
    return {
        "canonical_url": CANONICAL_URL,
        "source_listing_id": "persisted-1",
        "source_url": CANONICAL_URL,
        "canonical_source_url": CANONICAL_URL,
        "title": "Persisted Role",
        "company_norm": "acme",
        "location_raw": "Dublin, Ireland",
        "content_hash": "content-hash-persisted",
        "raw_hash": "raw-hash-persisted",
    }


async def test_listing_survives_an_engine_restart(migrated_db: Path) -> None:
    url = f"sqlite+aiosqlite:///{migrated_db}"
    first_seen = datetime(2026, 9, 1, tzinfo=UTC)

    engine_one = build_engine(url)
    maker_one = async_sessionmaker(engine_one, expire_on_commit=False)
    async with maker_one() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        await session.commit()
    async with maker_one() as session:
        await upsert_listing_source(
            session, source="linkedin", norm=_norm(), run_id=None, now=first_seen
        )
        await session.commit()
    await engine_one.dispose()

    # A brand-new engine on the same file. SQLite checkpoints on a clean close,
    # so the committed row is readable without the -wal sidecar.
    engine_two = build_engine(url)
    maker_two = async_sessionmaker(engine_two, expire_on_commit=False)
    async with maker_two() as session:
        row = await session.scalar(select(Listing).where(Listing.canonical_url == CANONICAL_URL))
    await engine_two.dispose()

    assert row is not None
    assert row.first_seen_at == first_seen.replace(tzinfo=None)


async def test_committed_data_is_readable_without_the_wal_sidecar(migrated_db: Path) -> None:
    """Copy only the main database file — no -wal/-shm — and read the row back."""
    url = f"sqlite+aiosqlite:///{migrated_db}"

    engine_one = build_engine(url)
    maker_one = async_sessionmaker(engine_one, expire_on_commit=False)
    async with maker_one() as session:
        session.add(Source(name="indeed", display_name="Indeed"))
        await session.commit()
    async with maker_one() as session:
        await upsert_listing_source(
            session,
            source="indeed",
            norm=_norm(),
            run_id=None,
            now=datetime(2026, 9, 1, tzinfo=UTC),
        )
        await session.commit()
    await engine_one.dispose()

    checkpointed = migrated_db.parent / "checkpointed-only.db"
    assert not checkpointed.exists()
    shutil.copy2(migrated_db, checkpointed)
    assert not Path(f"{checkpointed}-wal").exists()

    engine_two = build_engine(f"sqlite+aiosqlite:///{checkpointed}")
    maker_two = async_sessionmaker(engine_two, expire_on_commit=False)
    async with maker_two() as session:
        row = await session.scalar(select(Listing).where(Listing.canonical_url == CANONICAL_URL))
    await engine_two.dispose()

    assert row is not None
    assert row.title == "Persisted Role"
