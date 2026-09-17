"""PLAT-02 / D-12 — the `llm_calls` audit writer's shared read surface.

The repository never commits and validates its vocabulary before SQL (mirroring
the two CHECK constraints), and every read is total over a half-written row. These
tests pin the write, the latest-probe read the `/settings` page renders D-52's
detail from, and the per-run totals Phase 5's `_finish` caller consumes.

`latest_probe` / `llm_totals_for_run` are addressed through the module so the
target tests fail on a clear assertion while they are unimplemented.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import LlmCall, Run
from app.db.repositories import llm_call_repo
from app.db.repositories.llm_call_repo import record_llm_call

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 17, 12, 0, 5, tzinfo=UTC)


def _latest_probe():
    assert hasattr(llm_call_repo, "latest_probe"), (
        "app.db.repositories.llm_call_repo.latest_probe is not implemented yet"
    )
    return llm_call_repo.latest_probe


def _llm_totals_for_run():
    assert hasattr(llm_call_repo, "llm_totals_for_run"), (
        "app.db.repositories.llm_call_repo.llm_totals_for_run is not implemented yet"
    )
    return llm_call_repo.llm_totals_for_run


async def _count(
    session_factory: async_sessionmaker[AsyncSession], model: type
) -> int:
    async with session_factory() as session:
        return int(
            (await session.scalar(select(func.count()).select_from(model))) or 0
        )


async def _make_run(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        run = Run(trigger="manual", status="done", started_at=NOW)
        session.add(run)
        await session.commit()
        return int(run.id)


# --- vocabulary validation before SQL ------------------------------------------


async def test_an_unknown_purpose_raises_before_any_sql(
    session_factory: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    with pytest.raises(ValueError, match="unknown purpose"):
        await record_llm_call(db_session, purpose="bogus", status="ok")

    assert await _count(session_factory, LlmCall) == 0


async def test_an_unknown_status_raises(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="unknown status"):
        await record_llm_call(db_session, purpose="probe", status="bogus")


async def test_the_python_validation_is_stricter_than_the_check_constraint(
    db_session: AsyncSession,
) -> None:
    """A guard that cannot fail is not a guard: the bad value really is bad.

    The Python `ValueError` fires first; the CHECK constraint would also have
    refused the same value, so the stricter error is demonstrably the one in play.
    """
    with pytest.raises(ValueError, match="unknown purpose"):
        await record_llm_call(db_session, purpose="bogus", status="ok")

    db_session.add(LlmCall(purpose="bogus", status="ok", created_at=NOW))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


# --- the write contract --------------------------------------------------------


async def test_created_at_is_pinned_and_the_writer_never_commits(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as writer:
        record = await record_llm_call(writer, purpose="probe", status="ok", now=NOW)
        assert record.created_at == NOW
        # deliberately no commit

    assert await _count(session_factory, LlmCall) == 0


# --- latest_probe --------------------------------------------------------------


async def test_latest_probe_returns_the_most_recent_probe_row_only(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await record_llm_call(
            session, purpose="rank", status="ok", provider="other", now=LATER
        )
        await record_llm_call(
            session, purpose="probe", status="ok", provider="first", now=NOW
        )
        await record_llm_call(
            session, purpose="probe", status="ok", provider="second", now=LATER
        )
        await session.commit()

    async with session_factory() as session:
        record = await _latest_probe()(session)

    assert record is not None
    assert record.provider == "second"
    assert record.purpose == "probe"


async def test_latest_probe_is_none_on_an_empty_table(db_session: AsyncSession) -> None:
    assert await _latest_probe()(db_session) is None


async def test_latest_probe_breaks_a_same_timestamp_tie_by_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await record_llm_call(
            session, purpose="probe", status="ok", provider="first", now=NOW
        )
        second = await record_llm_call(
            session, purpose="probe", status="ok", provider="second", now=NOW
        )
        await session.commit()

    async with session_factory() as session:
        record = await _latest_probe()(session)

    assert record is not None
    assert record.id == second.id


async def test_server_version_round_trips_through_latest_probe(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await record_llm_call(
            session,
            purpose="probe",
            status="ok",
            server_version="1.18.31",
            now=NOW,
        )
        await session.commit()

    async with session_factory() as session:
        record = await _latest_probe()(session)

    assert record is not None
    assert record.server_version == "1.18.31"


# --- llm_totals_for_run --------------------------------------------------------


async def test_llm_totals_for_run_sums_only_that_runs_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _make_run(session_factory)
    other_run = await _make_run(session_factory)

    async with session_factory() as session:
        await record_llm_call(
            session,
            purpose="rank",
            status="ok",
            run_id=run_id,
            prompt_tokens=10,
            completion_tokens=5,
            now=NOW,
        )
        # A NULL completion count must contribute 0, not raise.
        await record_llm_call(
            session,
            purpose="rank",
            status="ok",
            run_id=run_id,
            prompt_tokens=2,
            completion_tokens=None,
            now=NOW,
        )
        await record_llm_call(
            session,
            purpose="rank",
            status="ok",
            run_id=other_run,
            prompt_tokens=100,
            completion_tokens=100,
            now=NOW,
        )
        await session.commit()

    async with session_factory() as session:
        totals = await _llm_totals_for_run()(session, run_id=run_id)

    assert totals == (2, 17)


async def test_llm_totals_for_run_is_zero_for_a_run_with_no_calls(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _make_run(session_factory)

    async with session_factory() as session:
        assert await _llm_totals_for_run()(session, run_id=run_id) == (0, 0)


async def test_a_null_run_probe_never_appears_in_run_totals(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _make_run(session_factory)

    async with session_factory() as session:
        await record_llm_call(
            session,
            purpose="probe",
            status="ok",
            run_id=None,
            prompt_tokens=99,
            completion_tokens=99,
            now=NOW,
        )
        await session.commit()

    async with session_factory() as session:
        assert await _llm_totals_for_run()(session, run_id=run_id) == (0, 0)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
