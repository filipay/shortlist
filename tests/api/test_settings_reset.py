"""The reset deletes the corpus and nothing else, and it refuses more than it allows."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.settings import RESET_DELETE_ORDER, RESET_KEPT_TABLES
from app.db.models import (
    CvArtifact,
    CvVersion,
    FilterRule,
    Listing,
    Run,
    Search,
    Source,
)
from app.db.repositories.listing_repo import upsert_listing_source
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


async def _seed_corpus(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, int]:
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        search = Search(
            name="Dublin Python",
            enabled=True,
            is_default=False,
            criteria_json={"keywords": "python"},
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(search)
        run = Run(
            search_id=None,
            trigger="manual",
            status="done",
            started_at=NOW,
            finished_at=NOW,
            fetched_count=1,
        )
        session.add(run)
        await session.commit()
        search_id = int(search.id)
        run_id = int(run.id)

    # A `filter_rules` row is seeded explicitly: it is a kept table, and the search row
    # alone would not give the "configuration is kept" assertion a rule to find.
    async with session_factory() as session:
        session.add(
            FilterRule(
                search_id=search_id,
                kind="location",
                params_json={"location": "Dublin, Ireland"},
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await session.commit()

    raw = RawListing(
        source="linkedin",  # type: ignore[arg-type]
        source_listing_id="linkedin-1",
        source_url="https://linkedin.example.com/jobs/1",
        direct_url=None,
        title="Backend Engineer",
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
    )
    async with session_factory() as session:
        await upsert_listing_source(
            session,
            source="linkedin",
            norm=normalise_listing(raw),
            run_id=run_id,
            now=NOW,
        )
        await session.commit()

    return {"run_id": run_id}


async def _count(session_factory: async_sessionmaker[AsyncSession], table: str) -> int:
    from app.db.models import Base

    async with session_factory() as session:
        return int(
            await session.scalar(
                select(func.count()).select_from(Base.metadata.tables[table])
            )
            or 0
        )


def _database_path(session_factory: async_sessionmaker[AsyncSession]) -> str:
    """The on-disk database file, read from the engine the app actually uses.

    `AsyncSession.get_bind()` returns the SYNC engine, whose `url.database` is the
    absolute path — verified against SQLAlchemy 2.0 + aiosqlite. In production that is
    `/data/jobsearch.db`; under pytest it is the temp copy, so the reset route needs no
    test-only override to find the file it must snapshot.
    """
    engine = session_factory.kw["bind"]
    return str(engine.sync_engine.url.database)


async def test_a_wrong_confirm_token_changes_nothing(client, session_factory) -> None:
    await _seed_corpus(session_factory)
    before = await _count(session_factory, "listings")

    response = await client.post("/settings/reset", data={"confirm": "delete"})

    assert response.status_code == 400
    assert "must type" in response.text.lower() or "DELETE" in response.text
    assert await _count(session_factory, "listings") == before


async def test_a_correct_token_empties_the_corpus_and_keeps_configuration(
    client, session_factory
) -> None:
    await _seed_corpus(session_factory)

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    assert response.status_code == 200
    for table in RESET_DELETE_ORDER:
        assert await _count(session_factory, table) == 0, table
    for table in RESET_KEPT_TABLES:
        assert await _count(session_factory, table) > 0, table


async def test_the_snapshot_holds_the_pre_reset_rows(client, session_factory) -> None:
    await _seed_corpus(session_factory)

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    backups = Path(_database_path(session_factory)).parent / "reset-backups"
    snapshots = sorted(backups.glob("*.db"))
    assert len(snapshots) == 1
    assert snapshots[0].name in response.text

    connection = sqlite3.connect(f"file:{snapshots[0]}?mode=ro", uri=True)
    try:
        assert connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
    finally:
        connection.close()


async def test_a_run_in_flight_blocks_the_reset(client, session_factory) -> None:
    await _seed_corpus(session_factory)
    async with session_factory() as session:
        session.add(
            Run(
                search_id=None,
                trigger="manual",
                status="running",
                started_at=NOW,
                fetched_count=0,
            )
        )
        await session.commit()

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    assert response.status_code == 409
    assert await _count(session_factory, "listings") == 1


async def test_tracked_work_blocks_the_reset(client, session_factory) -> None:
    await _seed_corpus(session_factory)
    async with session_factory() as session:
        session.add(CvVersion(label="Base", created_at=NOW))
        await session.commit()
    async with session_factory() as session:
        version = await session.scalar(select(CvVersion))
        listing = await session.scalar(select(Listing))
        assert version is not None and listing is not None
        session.add(
            CvArtifact(
                listing_id=listing.id,
                base_cv_version_id=version.id,
                compile_status="ok",
                created_at=NOW,
            )
        )
        await session.commit()

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    assert response.status_code == 409
    assert await _count(session_factory, "cv_artifacts") == 1


async def test_a_terminal_run_does_not_block_the_reset(client, session_factory) -> None:
    await _seed_corpus(session_factory)

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    assert response.status_code == 200
    assert await _count(session_factory, "runs") == 0
