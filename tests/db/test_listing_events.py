"""QUEUE-08 / D-41 / T-02-36 — append-only at both ends, and one projection query.

`tests/db/test_migration_contract.py::test_listing_events_append_only` already proves
the database refuses a mutation. This lane extends that guarantee to the repository
boundary (no code path even *attempts* one), and pins the projection rules that are
otherwise invisible: which event pairs each flag reads, the `(occurred_at, id)`
tie-break, and the fact that a `view` never changes the saved or hidden state.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.models import ListingEvent, Source
from app.db.repositories import event_repo
from app.db.repositories.listing_repo import upsert_listing_source
from app.pipeline.stages import normalise_listing
from app.sources.base import RawListing

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


@contextmanager
def _record_statements(engine: AsyncEngine) -> Iterator[list[str]]:
    """Capture every statement SQLAlchemy executes while the block is open."""
    recorded: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        recorded.append(statement)

    sa_event.listen(engine.sync_engine, "before_cursor_execute", _record)
    try:
        yield recorded
    finally:
        sa_event.remove(engine.sync_engine, "before_cursor_execute", _record)


async def _seed_listing(
    session_factory: async_sessionmaker[AsyncSession], *, index: int = 1
) -> int:
    """One listing, plus the `sources` row its `listing_sources` FK needs (once).

    Looked up by `name`, not by the primary key: `sources.name` is UNIQUE but the PK
    is a surrogate `id`, so `session.get(Source, "linkedin")` would never match.
    """
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
            session,
            source="linkedin",
            norm=normalise_listing(raw),
            run_id=None,
            now=NOW,
        )
        listing_id = int(outcome.listing_id)
        await session.commit()
    return listing_id


async def _append(
    session_factory: async_sessionmaker[AsyncSession],
    listing_id: int,
    event_type: str,
    *,
    when: datetime = NOW,
    context: dict | None = None,
) -> int:
    async with session_factory() as session:
        event = await event_repo.append_event(
            session,
            listing_id=listing_id,
            event_type=event_type,
            now=when,
            context=context,
        )
        event_id = int(event.id)
        await session.commit()
    return event_id


async def _state(
    session_factory: async_sessionmaker[AsyncSession], listing_ids: list[int]
) -> dict[int, event_repo.ListingState]:
    async with session_factory() as session:
        return await event_repo.state_for_listings(session, listing_ids=listing_ids)


async def _rows(session_factory: async_sessionmaker[AsyncSession]) -> list[ListingEvent]:
    async with session_factory() as session:
        return (
            (await session.execute(select(ListingEvent).order_by(ListingEvent.id)))
            .scalars()
            .all()
        )


# --- append-only, at the repository boundary ----------------------------------


async def test_append_event_issues_no_update_or_delete(
    session_factory: async_sessionmaker[AsyncSession], db_engine: AsyncEngine
) -> None:
    """T-02-36: the repository cannot fake a state, because it never mutates a row."""
    listing_id = await _seed_listing(session_factory)

    with _record_statements(db_engine) as recorded:
        await _append(session_factory, listing_id, "save")

    offenders = [
        statement
        for statement in recorded
        if "listing_events" in statement.lower()
        and ("update" in statement.lower() or "delete" in statement.lower())
    ]
    assert offenders == [], f"the repository mutated the event log: {offenders}"
    assert any("INSERT INTO listing_events" in statement for statement in recorded), (
        "the probe recorded no insert — the listener is not measuring what it claims"
    )


async def test_the_database_aborts_an_update_and_a_delete_of_an_event(
    migrated_db: Path, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The Phase-1 triggers, re-asserted here: a migration that dropped them fails here."""
    listing_id = await _seed_listing(session_factory)
    await _append(session_factory, listing_id, "save")

    connection = sqlite3.connect(migrated_db)
    try:
        with pytest.raises(sqlite3.IntegrityError) as update_error:
            connection.execute("UPDATE listing_events SET event_type = 'view'")
        assert "append-only" in str(update_error.value)

        with pytest.raises(sqlite3.IntegrityError) as delete_error:
            connection.execute("DELETE FROM listing_events")
        assert "append-only" in str(delete_error.value)
    finally:
        connection.close()


async def test_the_orm_cannot_update_or_delete_an_event_either(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The enforcement is the database's, not the ORM's good manners."""
    listing_id = await _seed_listing(session_factory)
    await _append(session_factory, listing_id, "save")

    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(text("UPDATE listing_events SET event_type = 'view'"))
        await session.rollback()

    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(text("DELETE FROM listing_events"))
        await session.rollback()

    rows = await _rows(session_factory)
    assert [row.event_type for row in rows] == ["save"], "the event survived intact"


# --- the projection, flag by flag ---------------------------------------------


async def test_save_then_unsave_projects_unsaved(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)
    await _append(session_factory, listing_id, "save")
    await _append(session_factory, listing_id, "unsave", when=NOW + timedelta(minutes=1))

    state = (await _state(session_factory, [listing_id]))[listing_id]

    assert state.saved is False
    assert state.hidden is False


async def test_hide_then_unhide_projects_visible(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)
    await _append(session_factory, listing_id, "hide")
    await _append(session_factory, listing_id, "unhide", when=NOW + timedelta(minutes=1))

    state = (await _state(session_factory, [listing_id]))[listing_id]

    assert state.hidden is False


async def test_only_save_projects_saved_and_not_hidden(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)
    await _append(session_factory, listing_id, "save")

    state = (await _state(session_factory, [listing_id]))[listing_id]

    assert state.saved is True
    assert state.hidden is False, "saving is not hiding (D-41)"


async def test_only_hide_projects_hidden_and_not_saved(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)
    await _append(session_factory, listing_id, "hide")

    state = (await _state(session_factory, [listing_id]))[listing_id]

    assert state.hidden is True
    assert state.saved is False, "hiding is not saving (D-41)"


async def test_a_shortlist_is_kept_until_an_unsave_contradicts_it(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The documented chosen semantics for the unwired `shortlist` type."""
    listing_id = await _seed_listing(session_factory)
    await _append(session_factory, listing_id, "shortlist")

    assert (await _state(session_factory, [listing_id]))[listing_id].shortlisted is True

    await _append(session_factory, listing_id, "save", when=NOW + timedelta(minutes=1))
    assert (await _state(session_factory, [listing_id]))[listing_id].shortlisted is True, (
        "a save does not clear a shortlist"
    )

    await _append(session_factory, listing_id, "unsave", when=NOW + timedelta(minutes=2))
    assert (await _state(session_factory, [listing_id]))[listing_id].shortlisted is False, (
        "an unsave drops the stronger shortlist with it"
    )


# --- the tie-break ------------------------------------------------------------


async def test_an_identical_occurred_at_is_broken_by_the_higher_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Two clicks in one second are the norm, so this must be deterministic."""
    listing_id = await _seed_listing(session_factory)

    await _append(session_factory, listing_id, "save", when=NOW)
    second = await _append(session_factory, listing_id, "unsave", when=NOW)

    state = (await _state(session_factory, [listing_id]))[listing_id]
    assert state.saved is False, "the later INSERT wins"

    # ... and with the insertion order reversed, the projection flips with it.
    other = await _seed_listing(session_factory, index=2)
    await _append(session_factory, other, "unsave", when=NOW)
    last = await _append(session_factory, other, "save", when=NOW)

    assert last > second  # the ids really are ordered by insertion
    assert (await _state(session_factory, [other]))[other].saved is True


# --- view does not affect the flags -------------------------------------------


async def test_a_view_after_a_hide_leaves_the_listing_hidden_but_records_the_view(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The least obvious rule in the projection, so it is pinned explicitly."""
    listing_id = await _seed_listing(session_factory)
    await _append(session_factory, listing_id, "hide")
    await _append(session_factory, listing_id, "view", when=NOW + timedelta(minutes=1))

    state = (await _state(session_factory, [listing_id]))[listing_id]

    assert state.hidden is True, "'I looked at it' is not 'put it back'"
    assert state.viewed is True
    assert state.last_viewed_at is not None


async def test_a_view_after_a_save_leaves_the_listing_saved(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)
    await _append(session_factory, listing_id, "save")
    await _append(session_factory, listing_id, "view", when=NOW + timedelta(minutes=1))

    state = (await _state(session_factory, [listing_id]))[listing_id]

    assert state.saved is True


# --- boundaries ---------------------------------------------------------------


async def test_a_listing_with_no_events_has_a_present_no_state_entry(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """An explicit value, not a missing key: "no events" must not look "unreadable"."""
    listing_id = await _seed_listing(session_factory)

    state = await _state(session_factory, [listing_id])

    assert listing_id in state
    assert state[listing_id] == event_repo.NO_STATE
    assert state[listing_id].saved is False and state[listing_id].hidden is False


async def test_an_unknown_listing_id_still_gets_an_entry(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    state = await _state(session_factory, [4242])

    assert state == {4242: event_repo.NO_STATE}


async def test_an_empty_id_list_returns_empty_without_a_query(
    session_factory: async_sessionmaker[AsyncSession], db_engine: AsyncEngine
) -> None:
    with _record_statements(db_engine) as recorded:
        async with session_factory() as session:
            result = await event_repo.state_for_listings(session, listing_ids=[])

    assert result == {}
    assert recorded == [], "an empty id list must not reach the database"


# --- the one-query contract ---------------------------------------------------


async def test_state_for_a_whole_page_is_one_query(
    session_factory: async_sessionmaker[AsyncSession], db_engine: AsyncEngine
) -> None:
    """Five listings with several events each must cost ONE statement, not five."""
    ids = [await _seed_listing(session_factory, index=index) for index in range(1, 6)]
    for offset, listing_id in enumerate(ids):
        await _append(session_factory, listing_id, "save", when=NOW)
        await _append(
            session_factory,
            listing_id,
            "hide",
            when=NOW + timedelta(seconds=offset + 1),
        )
        await _append(
            session_factory,
            listing_id,
            "view",
            when=NOW + timedelta(seconds=offset + 2),
        )

    with _record_statements(db_engine) as recorded:
        async with session_factory() as session:
            state = await event_repo.state_for_listings(session, listing_ids=ids)

    event_statements = [s for s in recorded if "listing_events" in s.lower()]
    assert len(event_statements) == 1, (
        f"the page projection must be one query, saw {len(event_statements)}: {event_statements}"
    )
    assert len(state) == len(ids)
    assert all(entry.saved and entry.hidden for entry in state.values())


async def test_latest_state_matches_the_page_projection(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The single-listing convenience and the page fold are the same code path."""
    listing_id = await _seed_listing(session_factory)
    await _append(session_factory, listing_id, "save")
    await _append(session_factory, listing_id, "hide", when=NOW + timedelta(minutes=1))

    async with session_factory() as session:
        single = await event_repo.latest_state(session, listing_id=listing_id)

    assert single == (await _state(session_factory, [listing_id]))[listing_id]
    assert single.saved is True and single.hidden is True


# --- context_json is machine facts only ---------------------------------------


async def test_context_json_round_trips_and_carries_no_listing_text(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    listing_id = await _seed_listing(session_factory)

    await _append(
        session_factory, listing_id, "save", context={"surface": "queue"}
    )

    rows = await _rows(session_factory)
    assert len(rows) == 1
    assert rows[0].context_json == {"surface": "queue"}
    assert "Build the thing" not in json.dumps(rows[0].context_json)
    assert "Engineer 1" not in json.dumps(rows[0].context_json)


async def test_an_unknown_event_type_is_rejected_by_the_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The vocabulary is validated in code as well as by the database CHECK."""
    listing_id = await _seed_listing(session_factory)

    async with session_factory() as session:
        with pytest.raises(ValueError) as error:
            await event_repo.append_event(
                session, listing_id=listing_id, event_type="promote", now=NOW
            )
        assert "promote" in str(error.value)

    assert await _rows(session_factory) == []


def test_the_event_vocabulary_mirrors_the_database_check() -> None:
    """A second vocabulary would be a second source of truth."""
    assert event_repo.EVENT_TYPES == (
        "save",
        "unsave",
        "hide",
        "unhide",
        "shortlist",
        "view",
    )
    assert set(event_repo.SAVE_EVENTS) | set(event_repo.HIDE_EVENTS) <= set(
        event_repo.EVENT_TYPES
    )
