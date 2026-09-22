"""`_finish`'s LLM-counter seam, and the D-94 optional-ranking posture.

`runs.llm_calls` and `runs.llm_tokens` exist, `_finish` can record them, and the
ranking task (plan 05-02) is the caller that supplies the totals
`llm_call_repo.llm_totals_for_run` returns. `ranked_count` is owned by the ranking
task (D-89), never by `_finish`.

**D-102 supersedes D-49.** D-49's "no automatic per-run LLM stage" was scoped to
Phase 3 and named Phase 5 as ranking's owner, so a full `run_pipeline` now reaches
the detached ranking task. The zero-`llm_calls` result in the hermetic lane is the
D-94 SKIP POSTURE (ranking is optional — no fact store here), not the absence of a
caller. The guard below says so explicitly.

Two properties matter and are both pinned here:

* an omitted counter must PRESERVE the recorded value, never zero it — a later
  non-LLM run must not erase what an LLM run recorded;
* `ranked_count` is untouched by this phase entirely (Phase 5 owns it).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import LlmCall, Run, Search, Source
from app.pipeline.run import _finish, run_pipeline
from tests.pipeline.test_filter_stage import OneListingAdapter
from tests.pipeline.test_injection_finding import _raw
from tests.pipeline.test_rank_optional import drain_ranking_tasks

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


# --- the D-94 optional posture (D-102 rewrite) ---------------------------------


async def test_a_pipeline_run_writes_zero_llm_calls(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The zero count is the D-94 posture, not "no LLM caller is wired".

    The run reaches the ranking task; the task finds no fact store and returns
    early; the result is zero `llm_calls` rows with no `purpose="rank"` row.
    Asserting the task entry point was REACHED is what distinguishes this from the
    retired D-49 wording — a future reader must not restore "the pipeline makes no
    model call" as the reason.
    """
    from app.pipeline import rank as rank_module

    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))  # no cv.yaml here
    monkeypatch.setattr(rank_module, "_RANKING_TASK", None)

    reached: list[int] = []
    real_run_ranking = rank_module.run_ranking

    async def _spy(*args: object, **kwargs: object) -> None:
        reached.append(1)
        await real_run_ranking(*args, **kwargs)

    monkeypatch.setattr(rank_module, "run_ranking", _spy)

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
    await drain_ranking_tasks()

    async with session_factory() as session:
        calls = int(
            await session.scalar(select(func.count()).select_from(LlmCall)) or 0
        )
        rank_rows = int(
            await session.scalar(
                select(func.count())
                .select_from(LlmCall)
                .where(LlmCall.purpose == "rank")
            )
            or 0
        )
    assert calls == 0
    assert rank_rows == 0, "the D-94 skip held: the task reached and returned early"
    assert reached, "the ranking task entry point was reached"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
