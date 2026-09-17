"""D-49 / Phase-5 seam — `_finish` can record the LLM counters, with no caller.

`runs.llm_calls` and `runs.llm_tokens` exist and nothing writes them. Phase 3 must
NOT make the pipeline call an LLM (D-49), so the honest deliverable is the WRITER
SEAM plus a direct unit test: Phase 5's ranking caller will pass the totals
`llm_call_repo.llm_totals_for_run` returns.

Two properties matter and are both pinned here:

* an omitted counter must PRESERVE the recorded value, never zero it — a later
  non-LLM run must not erase what an LLM run recorded;
* `ranked_count` is untouched by this phase entirely (Phase 5 owns it).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import LlmCall, Run, Search, Source
from app.pipeline.run import _finish, run_pipeline
from tests.pipeline.test_filter_stage import OneListingAdapter
from tests.pipeline.test_injection_finding import _raw

NOW = datetime(2026, 9, 1, tzinfo=UTC)


async def _make_run(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        run = Run(trigger="manual", status="running", started_at=NOW)
        session.add(run)
        await session.commit()
        return int(run.id)


async def _get_run(
    session_factory: async_sessionmaker[AsyncSession], run_id: int
) -> Run:
    async with session_factory() as session:
        run = await session.get(Run, run_id)
    assert run is not None
    return run


# --- the seam ------------------------------------------------------------------


async def test_finish_persists_the_llm_counters_when_supplied(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _make_run(session_factory)

    await _finish(
        session_factory,
        run_id,
        status="done",
        source_counts={},
        errors=[],
        llm_calls=3,
        llm_tokens=1234,
    )

    run = await _get_run(session_factory, run_id)
    assert run.llm_calls == 3
    assert run.llm_tokens == 1234


async def test_an_omitted_counter_preserves_the_recorded_value(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A non-LLM run must not zero what an LLM run recorded."""
    run_id = await _make_run(session_factory)
    await _finish(
        session_factory,
        run_id,
        status="partial",
        source_counts={},
        errors=[],
        llm_calls=5,
        llm_tokens=99,
    )

    await _finish(
        session_factory, run_id, status="done", source_counts={}, errors=[]
    )

    run = await _get_run(session_factory, run_id)
    assert run.llm_calls == 5
    assert run.llm_tokens == 99
    assert run.llm_calls != 0, "an omitted counter must not default to zero"


async def test_finish_never_writes_ranked_count(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run_id = await _make_run(session_factory)

    await _finish(
        session_factory,
        run_id,
        status="done",
        source_counts={},
        errors=[],
        llm_calls=1,
        llm_tokens=2,
    )

    run = await _get_run(session_factory, run_id)
    assert run.ranked_count is None, "Phase 5 owns the ranking count"


async def test_the_preservation_claim_can_actually_fail(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A guard that cannot fail is not a guard.

    A fresh run that was never given counters must NOT come back carrying the
    sentinel value, so "preserved" cannot pass against an accidental default.
    """
    run_id = await _make_run(session_factory)

    await _finish(session_factory, run_id, status="done", source_counts={}, errors=[])

    run = await _get_run(session_factory, run_id)
    assert run.llm_calls != 5
    assert run.llm_calls is None


# --- D-49 still holds ----------------------------------------------------------


async def test_a_pipeline_run_writes_zero_llm_calls(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The same guard as tests/pipeline/test_filter_stage.py:197, through this harness."""
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="Linkedin"))
        session.add(
            Search(
                name="Dublin Python",
                enabled=True,
                is_default=True,
                criteria_json={"keywords": "python"},
                version=1,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await session.commit()

    adapter = OneListingAdapter("linkedin", _raw(description="Build the thing."))

    await run_pipeline("manual", None, session_factory, adapters=[adapter])

    async with session_factory() as session:
        calls = int(
            await session.scalar(select(func.count()).select_from(LlmCall)) or 0
        )
    assert calls == 0, "Phase 3 must not wire an LLM caller into the pipeline (D-49)"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
