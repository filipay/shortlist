"""D-94 / D-102 — ranking is optional; ingest always succeeds unranked.

Three independent conditions make the ranking task a no-op that writes zero
`llm_calls` and zero `scores` rows: ranking disabled in Settings (the operator off
switch), no fact store, and an unreadable fact store. In every case
`run_pipeline` completes normally and `runs.status` is `"done"` — hitting a
deliberate skip is not a failure.

The fourth case pins the single-flight lifecycle: a run whose ranking would overlap
an in-flight task is skipped, not queued.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import LlmCall, Run, Score, Source
from app.pipeline import rank as rank_module
from app.pipeline.run import run_pipeline
from tests.pipeline.test_filter_stage import OneListingAdapter
from tests.pipeline.test_injection_finding import _raw


async def drain_ranking_tasks() -> None:
    """Await every in-flight detached ranking task.

    The task is fire-and-forget by design (D-88), so a test that asserts on its
    effects must let it finish. The set self-discards on completion; the bounded
    loop only guards against a pathological task that never finishes.
    """
    for _ in range(100):
        pending = list(rank_module._BACKGROUND_TASKS)
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)
        await asyncio.sleep(0)


@pytest.fixture(autouse=True)
def _reset_rank_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The single-flight guard and the in-flight counter are module-level state."""
    monkeypatch.setattr(rank_module, "_RANKING_TASK", None)
    monkeypatch.setattr(rank_module, "_in_flight", 0)
    yield
    monkeypatch.setattr(rank_module, "_RANKING_TASK", None)
    monkeypatch.setattr(rank_module, "_in_flight", 0)


async def _run_with_one_listing(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="Linkedin"))
        await session.commit()
    adapter = OneListingAdapter("linkedin", _raw(description="Build the thing."))
    return await run_pipeline("manual", None, session_factory, adapters=[adapter])


async def _assert_skipped(
    session_factory: async_sessionmaker[AsyncSession], run_id: int
) -> None:
    async with session_factory() as session:
        run = await session.get(Run, run_id)
        calls = int(await session.scalar(select(func.count()).select_from(LlmCall)) or 0)
        scores = int(await session.scalar(select(func.count()).select_from(Score)) or 0)

    assert run is not None
    assert run.status == "done", "a deliberate skip is not a failure"
    assert calls == 0
    assert scores == 0


# --- the three skip paths ------------------------------------------------------


async def test_ranking_disabled_writes_nothing_and_the_run_is_done(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ranking_enabled", False)

    run_id = await _run_with_one_listing(session_factory)
    await drain_ranking_tasks()

    await _assert_skipped(session_factory, run_id)


async def test_no_fact_store_writes_nothing_and_the_run_is_done(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An empty directory: cv.yaml is absent.
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))

    run_id = await _run_with_one_listing(session_factory)
    await drain_ranking_tasks()

    await _assert_skipped(session_factory, run_id)


async def test_unreadable_fact_store_writes_nothing_and_the_run_is_done(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / rank_module.CV_FILENAME).write_text("[[[ not valid yaml", encoding="utf-8")
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))

    run_id = await _run_with_one_listing(session_factory)
    await drain_ranking_tasks()

    await _assert_skipped(session_factory, run_id)


async def test_non_utf8_fact_store_writes_nothing_and_the_run_is_done(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The other half of the documented "absent or unreadable" condition: the file
    # exists but cannot be decoded as UTF-8. It must reach the same clean skip, not
    # escape the detached task as a raw UnicodeDecodeError.
    (tmp_path / rank_module.CV_FILENAME).write_bytes(b"\xff\xfe\x00\x01 not utf-8")
    monkeypatch.setattr(settings, "cv_dir", str(tmp_path))

    # Wrap the run as well as the drain: run_pipeline starts the detached ranking
    # task BEFORE _finish and keeps awaiting, so the skip log can be emitted before
    # _run_with_one_listing returns — capturing only the drain would be racy.
    with structlog.testing.capture_logs() as events:
        run_id = await _run_with_one_listing(session_factory)
        await drain_ranking_tasks()

    await _assert_skipped(session_factory, run_id)
    assert any(
        entry.get("event") == "pipeline.rank_skipped"
        and entry.get("reason") == "fact_store_absent"
        for entry in events
    )


# --- the single-flight lifecycle -----------------------------------------------


async def test_a_second_start_is_skipped_while_one_is_live(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def _slow(*args: object, **kwargs: object) -> None:
        started.set()
        await release.wait()

    monkeypatch.setattr(rank_module, "run_ranking", _slow)

    rank_module.start_ranking_task(101, session_factory)
    await started.wait()

    rank_module.start_ranking_task(102, session_factory)
    assert len(rank_module._BACKGROUND_TASKS) == 1, (
        "start-or-skip: a second ranking task must not be started while one is live"
    )

    release.set()
    await asyncio.gather(*list(rank_module._BACKGROUND_TASKS), return_exceptions=True)
