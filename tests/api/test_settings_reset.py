"""The reset deletes the corpus and nothing else, and it refuses more than it allows."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import settings
from app.api.settings import RESET_DELETE_ORDER, RESET_KEPT_TABLES
from app.db.models import (
    Application,
    ApplyConfig,
    CvArtifact,
    CvDraft,
    CvVersion,
    FilterRule,
    Listing,
    ListingDupe,
    ListingEvent,
    ListingExclusion,
    LlmCall,
    QueueState,
    RankingConfig,
    Run,
    Score,
    Search,
    Source,
    SourceRequestLog,
)
from app.db.repositories.listing_repo import upsert_listing_source
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    index: int,
    run_id: int | None = None,
) -> int:
    raw = RawListing(
        source="linkedin",  # type: ignore[arg-type]
        source_listing_id=f"linkedin-{index}",
        source_url=f"https://linkedin.example.com/jobs/{index}",
        direct_url=None,
        title=f"Backend Engineer {index}",
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
    )
    async with session_factory() as session:
        outcome = await upsert_listing_source(
            session,
            source="linkedin",
            norm=normalise_listing(raw),
            run_id=run_id,
            now=NOW,
        )
        await session.commit()
        return int(outcome.listing_id)


async def _seed_corpus(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, int]:
    """Seed ONE row (or more) into every table `RESET_DELETE_ORDER` names.

    The reset's deletes are only really exercised when each table is non-empty. This
    matters most for `listing_events`: its `BEFORE DELETE` trigger never fires on an
    empty table, which is exactly why an append-only abort shipped unnoticed.
    """
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

    first = await _seed_listing(session_factory, index=1, run_id=run_id)
    # A second listing gives `listing_dupes` two real endpoints to reference.
    second = await _seed_listing(session_factory, index=2, run_id=run_id)

    async with session_factory() as session:
        version = CvVersion(label="Base", created_at=NOW)
        session.add(version)
        session.add(QueueState(updated_at=NOW))
        # The global ranking weights document is a KEPT table (D-99): a corpus reset
        # must not discard the user's own configuration, so it gets a row here too.
        session.add(
            RankingConfig(id=1, weights_json={"evidence": 1.0}, updated_at=NOW)
        )
        # The screening-question document (migration 0006) is the same kind of kept
        # user config, so it gets a row too.
        session.add(
            ApplyConfig(id=1, questions_json={"questions": ["Why this role?"]}, updated_at=NOW)
        )
        session.add(
            Score(listing_id=first, run_id=run_id, criteria_version=1, created_at=NOW)
        )
        session.add(
            ListingExclusion(listing_id=first, run_id=run_id, created_at=NOW)
        )
        session.add_all(
            [
                ListingEvent(listing_id=first, event_type="view", occurred_at=NOW),
                ListingEvent(listing_id=first, event_type="save", occurred_at=NOW),
                ListingEvent(listing_id=second, event_type="view", occurred_at=NOW),
            ]
        )
        session.add(
            ListingDupe(
                listing_id=first,
                dup_listing_id=second,
                method="fuzzy",
                score=0.97,
                merged_at=NOW,
            )
        )
        session.add(LlmCall(run_id=run_id, purpose="rank", status="ok", created_at=NOW))
        session.add(
            SourceRequestLog(
                source="linkedin",
                run_id=run_id,
                occurred_at=NOW,
                kind="search",
                ok=True,
            )
        )
        await session.flush()
        version_id = int(version.id)
        # `cv_artifacts` and `cv_drafts` are DERIVED, regenerable side-tables of a
        # listing and live in `RESET_DELETE_ORDER`, so a reset must delete them.
        session.add(
            CvArtifact(
                listing_id=first,
                base_cv_version_id=version_id,
                compile_status="ok",
                created_at=NOW,
            )
        )
        session.add(
            CvDraft(
                listing_id=second,
                base_cv_version_id=version_id,
                patch_json={"ops": []},
                created_at=NOW,
            )
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
    # `cv_versions` is not in `RESET_KEPT_TABLES` (it is not shown on the page), but it
    # is the user's configuration and must survive the reset too.
    assert await _count(session_factory, "cv_versions") > 0


async def test_the_snapshot_holds_the_pre_reset_rows(client, session_factory) -> None:
    await _seed_corpus(session_factory)

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    backups = Path(_database_path(session_factory)).parent / "reset-backups"
    snapshots = sorted(backups.glob("*.db"))
    assert len(snapshots) == 1
    assert snapshots[0].name in response.text

    connection = sqlite3.connect(f"file:{snapshots[0]}?mode=ro", uri=True)
    try:
        assert connection.execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM listing_events").fetchone()[0] == 3
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
    assert await _count(session_factory, "listings") == 2


async def test_an_application_blocks_the_reset(client, session_factory) -> None:
    """`applications` is genuine user work, so a reset still refuses while it exists."""
    await _seed_corpus(session_factory)
    async with session_factory() as session:
        listing = await session.scalar(select(Listing))
        assert listing is not None
        session.add(
            Application(
                listing_id=listing.id,
                status="queued",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await session.commit()

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    assert response.status_code == 409
    assert await _count(session_factory, "applications") == 1
    # Refused before the first delete: nothing was removed.
    assert await _count(session_factory, "listings") == 2
    assert await _count(session_factory, "cv_artifacts") == 1


async def test_a_compiled_cv_artifact_does_not_block_and_is_deleted(
    client, session_factory
) -> None:
    """A `cv_artifacts` row is derived/regenerable, so the reset deletes it, not refuses."""
    await _seed_corpus(session_factory)
    assert await _count(session_factory, "cv_artifacts") == 1
    assert await _count(session_factory, "cv_drafts") == 1
    versions_before = await _count(session_factory, "cv_versions")
    assert versions_before > 0

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    assert response.status_code == 200
    assert await _count(session_factory, "cv_artifacts") == 0
    assert await _count(session_factory, "cv_drafts") == 0
    # `cv_versions` is a KEPT table: the artifact's FK does not force its deletion.
    assert await _count(session_factory, "cv_versions") == versions_before


async def test_a_terminal_run_does_not_block_the_reset(client, session_factory) -> None:
    await _seed_corpus(session_factory)

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    assert response.status_code == 200
    assert await _count(session_factory, "runs") == 0


async def test_a_failed_snapshot_deletes_nothing(
    client, session_factory, monkeypatch
) -> None:
    """The 500 branch: a snapshot that cannot be taken must leave every row intact."""
    await _seed_corpus(session_factory)
    before = {
        table: await _count(session_factory, table)
        for table in ("listings", "listing_sources", "runs", "searches")
    }
    assert all(count > 0 for count in before.values()), before

    def _fail_snapshot(**_kwargs: object) -> Path:
        raise settings.ResetRefused("disk full")

    monkeypatch.setattr(settings, "snapshot_database", _fail_snapshot)

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    assert response.status_code == 500
    assert "snapshot failed" in response.text.lower()
    for table, count in before.items():
        assert await _count(session_factory, table) == count, table


async def _trigger_present(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        return int(
            await session.scalar(
                text(
                    "SELECT count(*) FROM sqlite_master "
                    "WHERE type = 'trigger' AND name = 'listing_events_no_delete'"
                )
            )
            or 0
        )


async def test_the_append_only_trigger_is_re_armed_and_still_enforced(
    client, session_factory
) -> None:
    """The reset suspends the append-only DELETE trigger only to re-arm it on commit.

    Presence is not enough — a trigger that exists but is not enforced would be a false
    pass — so a fresh listing + event is inserted after the reset (the FK is checked on
    the event INSERT: the event must reference a listing that exists) and a direct
    DELETE must still abort.
    """
    await _seed_corpus(session_factory)
    assert await _count(session_factory, "listing_events") == 3

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    assert response.status_code == 200
    assert await _trigger_present(session_factory) == 1

    fresh = await _seed_listing(session_factory, index=999)
    async with session_factory() as session:
        session.add(ListingEvent(listing_id=fresh, event_type="view", occurred_at=NOW))
        await session.commit()

    with pytest.raises(IntegrityError):
        async with session_factory() as session:
            await session.execute(text("DELETE FROM listing_events"))
            await session.commit()

    assert await _count(session_factory, "listing_events") == 1, "the DELETE did not abort"


async def test_a_failed_delete_rolls_back_and_re_arms_the_trigger(
    client, session_factory, monkeypatch
) -> None:
    """A delete-phase error must roll back every DELETE and the DROP TRIGGER with it."""
    await _seed_corpus(session_factory)
    before = {
        table: await _count(session_factory, table)
        for table in ("listings", "listing_events", "listing_sources", "runs")
    }
    assert all(count > 0 for count in before.values()), before

    def _fail_delete(_table: object) -> object:
        raise RuntimeError("forced delete failure")

    # The route calls the imported `delete`; replacing it makes a delete raise without a
    # real disk error. The suspend has already run by then, so this also proves the DROP
    # is rolled back rather than left committed.
    monkeypatch.setattr(settings, "delete", _fail_delete)

    response = await client.post("/settings/reset", data={"confirm": "DELETE"})

    assert response.status_code == 500
    assert "nothing was deleted" in response.text.lower()
    for table, count in before.items():
        assert await _count(session_factory, table) == count, table
    assert await _trigger_present(session_factory) == 1
