"""APPLY-05 / D-131 — `application_events` is append-only at both ends.

`tests/db/test_migration_contract.py::test_screening_drafts_apply_config_and_application_events_append_only`
already proves the migrated DDL refuses a mutation. This lane extends the guarantee to
the repository boundary (the only writer is INSERT) and pins the one-event-per-transition
contract that keeps `applications.status` and its history from drifting.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Application, ApplicationEvent, Source
from app.db.repositories import application_repo
from app.db.repositories.listing_repo import upsert_listing_source
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession], *, index: int = 1
) -> int:
    async with session_factory() as session:
        exists = await session.scalar(select(Source.id).where(Source.name == "linkedin"))
        if exists is None:
            session.add(Source(name="linkedin", display_name="LinkedIn"))
            await session.commit()

    raw = RawListing(
        source="linkedin",  # type: ignore[arg-type]
        source_listing_id=f"linkedin-{index}",
        source_url=f"https://linkedin.example.com/jobs/{index}",
        direct_url=None,
        title=f"Engineer {index}",
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
    )
    async with session_factory() as session:
        outcome = await upsert_listing_source(
            session, source="linkedin", norm=normalise_listing(raw), run_id=None, now=NOW
        )
        listing_id = int(outcome.listing_id)
        await session.commit()
    return listing_id


async def _record(
    session_factory: async_sessionmaker[AsyncSession], listing_id: int, *, status: str = "queued"
) -> int:
    async with session_factory() as session:
        new_id = await application_repo.record_application(
            session,
            listing_id=listing_id,
            status=status,
            cv_artifact_id=None,
            notes=None,
            next_action_at=None,
            now=NOW,
        )
        await session.commit()
    assert new_id is not None
    return new_id


async def _event_count(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        return int(
            (await session.scalar(select(func.count()).select_from(ApplicationEvent))) or 0
        )


async def test_recording_appends_exactly_one_event(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)
    await _record(session_factory, listing_id)

    assert await _event_count(session_factory) == 1


async def test_each_transition_appends_exactly_one_event(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)
    app_id = await _record(session_factory, listing_id, status="shortlisted")

    async with session_factory() as session:
        await application_repo.transition_application(
            session,
            application_id=app_id,
            to_status="interviewing",
            note="Screen booked",
            now=NOW + timedelta(days=1),
        )
        await session.commit()

    assert await _event_count(session_factory) == 2

    async with session_factory() as session:
        events = (
            (await session.execute(select(ApplicationEvent).order_by(ApplicationEvent.id)))
            .scalars()
            .all()
        )
    assert [event.to_status for event in events] == ["shortlisted", "interviewing"]
    assert events[1].from_status == "shortlisted"
    assert events[1].note == "Screen booked"


async def test_the_database_aborts_an_update_and_a_delete_of_an_event(
    migrated_db: Path, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The migration's triggers, re-asserted here: dropping them fails this test."""
    listing_id = await _seed_listing(session_factory)
    await _record(session_factory, listing_id)

    connection = sqlite3.connect(migrated_db)
    try:
        with pytest.raises(sqlite3.IntegrityError) as update_error:
            connection.execute("UPDATE application_events SET to_status = 'applied'")
        assert "append-only" in str(update_error.value)

        with pytest.raises(sqlite3.IntegrityError) as delete_error:
            connection.execute("DELETE FROM application_events")
        assert "append-only" in str(delete_error.value)
    finally:
        connection.close()


async def test_the_orm_cannot_update_or_delete_an_event_either(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The enforcement is the database's, not the ORM's good manners."""
    listing_id = await _seed_listing(session_factory)
    await _record(session_factory, listing_id)

    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text("UPDATE application_events SET to_status = 'applied'")
            )
        await session.rollback()

    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(text("DELETE FROM application_events"))
        await session.rollback()

    async with session_factory() as session:
        events = (await session.execute(select(ApplicationEvent))).scalars().all()
    assert [event.to_status for event in events] == ["queued"], "the event survived intact"


async def test_the_application_row_follows_its_event(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The row's current status and its last event never disagree after a transition."""
    listing_id = await _seed_listing(session_factory)
    app_id = await _record(session_factory, listing_id, status="shortlisted")
    async with session_factory() as session:
        await application_repo.transition_application(
            session,
            application_id=app_id,
            to_status="applied",
            cv_artifact_id=None,
            note=None,
            now=NOW + timedelta(hours=1),
        )
        # A transition to `applied` without an `ok` artefact is a refusal: nothing changed.
        await session.commit()

    assert await _event_count(session_factory) == 1
    async with session_factory() as session:
        row = await session.get(Application, app_id)
    assert row is not None
    assert row.status == "shortlisted"


def test_the_status_vocabulary_mirrors_the_database_check() -> None:
    """A second vocabulary would be a second source of truth."""
    assert application_repo.APPLICATION_STATUSES == (
        "discovered",
        "queued",
        "shortlisted",
        "applied",
        "interviewing",
        "offer",
        "rejected",
        "withdrawn",
    )
    assert set(application_repo.TERMINAL_STATUSES) <= set(
        application_repo.APPLICATION_STATUSES
    )
