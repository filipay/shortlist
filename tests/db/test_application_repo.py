"""APPLY-03 / APPLY-04 / APPLY-05 / APPLY-06 — the application repository contract.

Observable truths:

1. `record_application` writes one `applications` row and exactly one `application_events`
   row (a NULL `from_status` → the recording stage).
2. An unknown status is a `ValueError` raised before any SQL — nothing is written.
3. `read_tracker` joins listing/company and reports the server-computed event count.
4. `read_history` returns events in chronological `(occurred_at, id)` order.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Application, ApplicationEvent, Source
from app.db.repositories import application_repo, cv_artifact_repo
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
        title=f"Backend Engineer {index}",
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


async def _seed_artifact(
    session_factory: async_sessionmaker[AsyncSession], listing_id: int, *, status: str = "ok"
) -> int:
    async with session_factory() as session:
        record = await cv_artifact_repo.insert_artifact(
            session,
            listing_id=listing_id,
            base_cv_version_id=None,
            patch_json={},
            change_log_json=[],
            compile_status=status,
            verification_json={},
            page_count=1 if status == "ok" else None,
            now=NOW,
        )
        await session.commit()
    return record.id


async def _counts(session_factory: async_sessionmaker[AsyncSession]) -> tuple[int, int]:
    async with session_factory() as session:
        applications = await session.scalar(select(func.count()).select_from(Application))
        events = await session.scalar(select(func.count()).select_from(ApplicationEvent))
    return int(applications or 0), int(events or 0)


async def test_record_writes_one_row_and_one_created_event(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)

    async with session_factory() as session:
        new_id = await application_repo.record_application(
            session,
            listing_id=listing_id,
            status="queued",
            cv_artifact_id=None,
            notes="Referred by a friend",
            next_action_at=NOW + timedelta(days=7),
            now=NOW,
        )
        await session.commit()

    assert new_id is not None
    assert await _counts(session_factory) == (1, 1)

    async with session_factory() as session:
        event = (await session.execute(select(ApplicationEvent))).scalar_one()
    assert event.application_id == new_id
    assert event.from_status is None
    assert event.to_status == "queued"


async def test_an_unknown_status_is_a_value_error_and_writes_nothing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)

    async with session_factory() as session:
        with pytest.raises(ValueError):
            await application_repo.record_application(
                session,
                listing_id=listing_id,
                status="promoted",
                cv_artifact_id=None,
                notes=None,
                next_action_at=None,
                now=NOW,
            )
        await session.rollback()

    assert await _counts(session_factory) == (0, 0)


async def test_read_tracker_joins_listing_and_company_and_counts_events(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)
    async with session_factory() as session:
        await application_repo.record_application(
            session,
            listing_id=listing_id,
            status="shortlisted",
            cv_artifact_id=None,
            notes=None,
            next_action_at=None,
            now=NOW,
        )
        await session.commit()

    async with session_factory() as session:
        rows = await application_repo.read_tracker(session, now=NOW)

    assert len(rows) == 1
    row = rows[0]
    assert row.listing_id == listing_id
    assert row.status == "shortlisted"
    assert row.listing_title == "Backend Engineer 1"
    assert row.company == "Acme"
    assert row.event_count == 1


async def test_read_history_is_chronological(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)
    async with session_factory() as session:
        app_id = await application_repo.record_application(
            session,
            listing_id=listing_id,
            status="shortlisted",
            cv_artifact_id=None,
            notes=None,
            next_action_at=None,
            now=NOW,
        )
        await session.commit()

    assert app_id is not None
    async with session_factory() as session:
        await application_repo.transition_application(
            session,
            application_id=int(app_id),
            to_status="interviewing",
            note="Screen booked",
            now=NOW + timedelta(days=1),
        )
        await session.commit()

    async with session_factory() as session:
        history = await application_repo.read_history(session, int(app_id))

    assert [event.to_status for event in history] == ["shortlisted", "interviewing"]
    assert [event.from_status for event in history] == [None, "shortlisted"]
    assert [event.occurred_at for event in history] == sorted(
        event.occurred_at for event in history
    )


async def _event_count(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        return int(
            (await session.scalar(select(func.count()).select_from(ApplicationEvent))) or 0
        )


async def test_applied_requires_ok_artifact(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """D-118/D-129: a blocked artefact is refused and writes nothing; an ok one links."""
    listing_id = await _seed_listing(session_factory)
    async with session_factory() as session:
        app_id = await application_repo.record_application(
            session,
            listing_id=listing_id,
            status="shortlisted",
            cv_artifact_id=None,
            notes=None,
            next_action_at=None,
            now=NOW,
        )
        await session.commit()
    assert app_id is not None

    blocked_id = await _seed_artifact(session_factory, listing_id, status="blocked")
    async with session_factory() as session:
        refused = await application_repo.transition_application(
            session,
            application_id=app_id,
            to_status="applied",
            cv_artifact_id=blocked_id,
            note=None,
            now=NOW,
        )
        await session.commit()

    assert refused is None, "a blocked artefact must not be attachable"
    async with session_factory() as session:
        row = await session.get(Application, app_id)
    assert row is not None and row.status == "shortlisted"
    assert await _event_count(session_factory) == 1, "a refusal writes no event"

    ok_id = await _seed_artifact(session_factory, listing_id, status="ok")
    async with session_factory() as session:
        accepted = await application_repo.transition_application(
            session,
            application_id=app_id,
            to_status="applied",
            cv_artifact_id=ok_id,
            note="sent",
            now=NOW,
        )
        await session.commit()

    assert accepted == app_id
    async with session_factory() as session:
        row = await session.get(Application, app_id)
    assert row is not None
    assert row.status == "applied"
    assert row.cv_artifact_id == ok_id
    assert row.applied_at is not None
    assert await _event_count(session_factory) == 2


async def test_tracker_read_keeps_the_stored_link_when_artifact_status_changes(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The ok-only predicate is attach-time only; the historical link is read unfiltered."""
    listing_id = await _seed_listing(session_factory)
    ok_id = await _seed_artifact(session_factory, listing_id, status="ok")
    async with session_factory() as session:
        app_id = await application_repo.record_application(
            session,
            listing_id=listing_id,
            status="applied",
            cv_artifact_id=ok_id,
            notes=None,
            next_action_at=None,
            now=NOW,
        )
        await session.commit()
    assert app_id is not None

    # A later, blocked artefact must NOT make the recorded link vanish.
    await _seed_artifact(session_factory, listing_id, status="blocked")

    async with session_factory() as session:
        rows = await application_repo.read_tracker(session, now=NOW)
    assert len(rows) == 1
    assert rows[0].cv_artifact_id == ok_id
