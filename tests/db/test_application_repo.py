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
    session_factory: async_sessionmaker[AsyncSession],
    *,
    index: int = 1,
    company: str = "Acme",
    title: str | None = None,
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
        title=title or f"Backend Engineer {index}",
        company_name=company,
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
        page = await application_repo.read_tracker(session, now=NOW)

    assert page.total == 1
    rows = page.rows
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


async def test_applied_refuses_an_ok_artifact_from_another_listing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """WR-02: the SQL `ok` gate is necessary but not sufficient.

    A crafted POST can name a verified artefact that belongs to a *different*
    listing. Both the record and the transition path must refuse it and write
    nothing (D-129's "the exact CV that was sent for THIS job").
    """
    listing_a = await _seed_listing(session_factory, index=1)
    listing_b = await _seed_listing(session_factory, index=2)
    other_ok = await _seed_artifact(session_factory, listing_b, status="ok")

    async with session_factory() as session:
        refused = await application_repo.record_application(
            session,
            listing_id=listing_a,
            status="applied",
            cv_artifact_id=other_ok,
            notes=None,
            next_action_at=None,
            now=NOW,
        )
        await session.commit()
    assert refused is None, "listing B's ok artefact must not attach to listing A"
    assert await _counts(session_factory) == (0, 0)

    async with session_factory() as session:
        app_id = await application_repo.record_application(
            session,
            listing_id=listing_a,
            status="shortlisted",
            cv_artifact_id=None,
            notes=None,
            next_action_at=None,
            now=NOW,
        )
        await session.commit()
    assert app_id is not None

    async with session_factory() as session:
        refused_transition = await application_repo.transition_application(
            session,
            application_id=app_id,
            to_status="applied",
            cv_artifact_id=other_ok,
            note=None,
            now=NOW,
        )
        await session.commit()
    assert refused_transition is None, "a foreign ok artefact must not attach"
    async with session_factory() as session:
        row = await session.get(Application, app_id)
    assert row is not None and row.status == "shortlisted"
    assert row.cv_artifact_id is None
    assert await _event_count(session_factory) == 1, "a refusal writes no event"


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
        page = await application_repo.read_tracker(session, now=NOW)
    assert page.total == 1
    assert page.rows[0].cv_artifact_id == ok_id


async def _record(
    session_factory: async_sessionmaker[AsyncSession],
    listing_id: int,
    *,
    status: str = "queued",
    notes: str | None = None,
) -> int:
    async with session_factory() as session:
        app_id = await application_repo.record_application(
            session,
            listing_id=listing_id,
            status=status,
            cv_artifact_id=None,
            notes=notes,
            next_action_at=None,
            now=NOW,
        )
        await session.commit()
    assert app_id is not None
    return int(app_id)


async def test_read_tracker_stage_filter(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """`stage` narrows the slice and survives the page structure."""
    a = await _seed_listing(session_factory, index=1)
    b = await _seed_listing(session_factory, index=2)
    await _record(session_factory, a, status="shortlisted")
    await _record(session_factory, b, status="queued")

    async with session_factory() as session:
        page = await application_repo.read_tracker(session, stage="shortlisted", now=NOW)
    assert [row.listing_id for row in page.rows] == [a]

    async with session_factory() as session:
        page = await application_repo.read_tracker(session, stage="queued", now=NOW)
    assert [row.listing_id for row in page.rows] == [b]


async def test_read_tracker_search_matches_company_title_and_notes(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """`q` is a casefold substring over company, title AND notes (T-07-04-01)."""
    a = await _seed_listing(session_factory, index=1, company="Acme")
    b = await _seed_listing(session_factory, index=2, company="Globex", title="Data Scientist 2")
    await _record(session_factory, a, notes="referred by a friend")
    await _record(session_factory, b)

    async def _ids(**kwargs: object) -> list[int]:
        async with session_factory() as session:
            page = await application_repo.read_tracker(session, now=NOW, **kwargs)  # type: ignore[arg-type]
        return [row.listing_id for row in page.rows]

    assert await _ids(q="acme") == [a], "a company hit"
    assert await _ids(q="data scientist") == [b], "a title hit"
    assert await _ids(q="REFERRED") == [a], "a notes hit, casefolded"
    assert await _ids(q="zzz") == [], "no false match"


async def test_read_tracker_unknown_stage_is_a_value_error(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """An unknown stage raises BEFORE SQL — never an empty result (T-07-04-01)."""
    async with session_factory() as session:
        with pytest.raises(ValueError):
            await application_repo.read_tracker(session, stage="promoted", now=NOW)


async def test_read_tracker_paginates_two_way(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """`offset`/`limit` slice the filtered set with QueuePage-style accessors."""
    for index in (1, 2, 3):
        listing_id = await _seed_listing(session_factory, index=index)
        await _record(session_factory, listing_id)

    async with session_factory() as session:
        first = await application_repo.read_tracker(session, offset=0, limit=2, now=NOW)
    assert first.total == 3
    assert len(first.rows) == 2
    assert first.has_prev is False
    assert first.has_more is True
    assert first.page_index == 1
    assert first.page_count == 2
    assert first.next_offset == 2

    async with session_factory() as session:
        second = await application_repo.read_tracker(session, offset=2, limit=2, now=NOW)
    assert len(second.rows) == 1
    assert second.has_prev is True
    assert second.has_more is False
    assert second.page_index == 2
    assert second.prev_offset == 0


def test_tracker_query_string_omits_offset_for_a_predicate_change() -> None:
    """A predicate change restarts the page; only the pager supplies an offset."""
    query = application_repo.TrackerQuery(
        q="acme", stage="shortlisted", view="needs_action", offset=25
    )
    predicate_change = query.query_string()
    assert "offset" not in predicate_change
    assert "q=acme" in predicate_change
    assert "stage=shortlisted" in predicate_change
    assert "view=needs_action" in predicate_change
    assert "offset=25" in query.query_string(offset=25)


async def test_needs_action_ordering(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """D-133: overdue first ascending, then upcoming, nulls last, terminal excluded."""
    listings = [
        await _seed_listing(session_factory, index=index) for index in range(1, 6)
    ]
    older_overdue, overdue, upcoming, undated, terminal = listings

    async def _app(listing_id: int, *, status: str, next_action: datetime | None) -> None:
        async with session_factory() as session:
            app_id = await application_repo.record_application(
                session,
                listing_id=listing_id,
                status=status,
                cv_artifact_id=None,
                notes=None,
                next_action_at=next_action,
                now=NOW,
            )
            await session.commit()
        assert app_id is not None

    await _app(overdue, status="shortlisted", next_action=NOW - timedelta(days=2))
    await _app(upcoming, status="shortlisted", next_action=NOW + timedelta(days=3))
    await _app(older_overdue, status="shortlisted", next_action=NOW - timedelta(days=5))
    await _app(undated, status="shortlisted", next_action=None)
    await _app(terminal, status="rejected", next_action=NOW - timedelta(days=1))

    async with session_factory() as session:
        page = await application_repo.read_tracker(session, view="needs_action", now=NOW)

    assert [row.listing_id for row in page.rows] == [
        older_overdue,
        overdue,
        upcoming,
        undated,
    ]
    assert page.total == 4, "the terminal application is excluded"
    assert [row.is_overdue for row in page.rows] == [True, True, False, False]
    assert all(row.listing_id != terminal for row in page.rows)


async def test_read_tracker_unknown_view_is_a_value_error(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        with pytest.raises(ValueError):
            await application_repo.read_tracker(session, view="urgent", now=NOW)


async def test_the_exact_cv_link_survives_every_later_transition(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """APPLY-04 failure class: the link to the exact CV sent must persist for life.

    The tracker only shows the `cv_artifact_id` picker for the `applied` stage, so every
    LATER stage move calls `transition_application(cv_artifact_id=None)`. A regression
    that re-initialised the link on that path would silently drop the exact-CV provenance
    on the first post-apply stage change, and every pre-existing test would still pass
    (they only pin the attach-time gate). This mutates the status through each later stage
    and asserts the id is byte-identical after each one.
    """
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

    for step, to_status in enumerate(("interviewing", "offer", "rejected"), start=1):
        async with session_factory() as session:
            moved = await application_repo.transition_application(
                session,
                application_id=app_id,
                to_status=to_status,
                cv_artifact_id=None,  # the later-stage form carries no picker value
                note=None,
                now=NOW + timedelta(days=step),
            )
            await session.commit()
        assert moved == app_id
        async with session_factory() as session:
            row = await session.get(Application, app_id)
        assert row is not None
        assert row.status == to_status
        assert row.cv_artifact_id == ok_id, (
            f"the exact-CV link was lost on the {to_status} transition"
        )
        assert row.applied_at is not None, "applied_at must survive later transitions"

    async with session_factory() as session:
        page = await application_repo.read_tracker(session, now=NOW)
    assert page.rows[0].cv_artifact_id == ok_id
