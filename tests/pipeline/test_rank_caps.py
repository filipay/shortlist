"""RANK-08 / D-91 / D-92 / D-93 — the spend ceilings refuse before the call.

A cap that is checked after the call is not a cap (LLM calls are the dominant
variable cost, PROJECT.md), so the property under test is: once either ceiling
would be reached, the backend records no further request. A refusal is a graceful
stop, not an error — the run is not marked failed and one refusal row records
which cap fired.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import LlmCall, Score
from app.db.repositories import llm_call_repo
from app.pipeline import rank as rank_module
from app.pipeline.rank import run_ranking
from tests.pipeline.test_rank_stage import StubBackend, _add_listing, _facts, _seed_run

BUDGET_MARKER = "budget_exceeded"


@pytest.fixture(autouse=True)
def _reset_in_flight(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The in-flight counter is module-level; a leaked slot would poison later tests."""
    monkeypatch.setattr(rank_module, "_in_flight", 0)
    yield
    monkeypatch.setattr(rank_module, "_in_flight", 0)


async def _seed_rank_call(
    session_factory: async_sessionmaker[AsyncSession], *, when: datetime
) -> None:
    async with session_factory() as session:
        await llm_call_repo.record_llm_call(
            session, purpose="rank", status="ok", now=when
        )
        await session.commit()


async def _rows(
    session_factory: async_sessionmaker[AsyncSession], model: type
) -> list:
    async with session_factory() as session:
        return list((await session.execute(select(model))).scalars().all())


# --- the per-run ceiling (RANK-08) ---------------------------------------------


async def test_cap_refuses_before_the_call(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ranking_max_calls_per_run", 1)
    monkeypatch.setattr(settings, "ranking_max_calls_per_day", 1000)

    run_id = await _seed_run(session_factory)
    await _add_listing(session_factory, title="First Role")
    await _add_listing(session_factory, title="Second Role")

    stub = StubBackend()
    await run_ranking(session_factory, run_id=run_id, llm=stub, facts=_facts())

    assert len(stub.calls) == 1, "the second call must be refused BEFORE it is issued"

    refusals = [
        row for row in await _rows(session_factory, LlmCall) if row.status == "error"
    ]
    assert len(refusals) == 1
    assert refusals[0].purpose == "rank"
    assert refusals[0].run_id == run_id
    assert refusals[0].error.startswith(BUDGET_MARKER)

    async with session_factory() as session:
        assert (
            await llm_call_repo.rank_cap_reason_for_run(session, run_id=run_id)
            == "per_run"
        )


async def test_the_ceiling_does_not_fire_below_the_cap(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ranking_max_calls_per_run", 10)
    monkeypatch.setattr(settings, "ranking_max_calls_per_day", 1000)

    run_id = await _seed_run(session_factory)
    await _add_listing(session_factory, title="First Role")
    await _add_listing(session_factory, title="Second Role")

    stub = StubBackend()
    await run_ranking(session_factory, run_id=run_id, llm=stub, facts=_facts())

    assert len(stub.calls) == 2
    assert await _rows(session_factory, Score) != []
    assert [
        row for row in await _rows(session_factory, LlmCall) if row.status == "error"
    ] == []


# --- the rolling-24h ceiling (D-91) --------------------------------------------


async def test_rolling_24h_cap_is_enforced(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ranking_max_calls_per_run", 100)
    monkeypatch.setattr(settings, "ranking_max_calls_per_day", 1)

    run_id = await _seed_run(session_factory)
    await _add_listing(session_factory, title="Role")

    # Pre-exhaust the trailing window with two rank calls an hour ago.
    in_window = datetime.now(UTC) - timedelta(hours=1)
    await _seed_rank_call(session_factory, when=in_window)
    await _seed_rank_call(session_factory, when=in_window)

    stub = StubBackend()
    await run_ranking(session_factory, run_id=run_id, llm=stub, facts=_facts())

    assert stub.calls == [], "the trailing window is already at its ceiling"

    async with session_factory() as session:
        assert (
            await llm_call_repo.rank_cap_reason_for_run(session, run_id=run_id)
            == "per_day"
        )


async def test_rank_calls_since_excludes_old_rows_and_other_purposes(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    recent = datetime.now(UTC) - timedelta(hours=1)
    stale = datetime.now(UTC) - timedelta(hours=25)
    async with session_factory() as session:
        await llm_call_repo.record_llm_call(session, purpose="rank", status="ok", now=recent)
        await llm_call_repo.record_llm_call(session, purpose="rank", status="ok", now=stale)
        await llm_call_repo.record_llm_call(session, purpose="probe", status="ok", now=recent)
        await session.commit()

    async with session_factory() as session:
        assert await llm_call_repo.rank_calls_since(session) == 1


# --- the reservation primitive (T-05-09) ---------------------------------------


async def test_reserve_returns_true_exactly_once_at_the_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rank_module, "_in_flight", 0)

    assert await rank_module._reserve(0, 0, cap_day=1, cap_run=1) is True
    assert await rank_module._reserve(0, 0, cap_day=1, cap_run=1) is False
    assert rank_module._in_flight == 1

    await rank_module._release()
    assert rank_module._in_flight == 0

    # A second release is harmless: the floor stops a double release from going
    # negative and suppressing a later reservation.
    await rank_module._release()
    assert rank_module._in_flight == 0


async def test_the_day_ceiling_fires_when_the_run_ceiling_has_room(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rank_module, "_in_flight", 0)

    assert await rank_module._reserve(5, 0, cap_day=5, cap_run=100) is False
    assert await rank_module._reserve(4, 0, cap_day=5, cap_run=100) is True
    await rank_module._release()
