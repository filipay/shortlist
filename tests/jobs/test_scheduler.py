"""The scheduler contract: the target runs the pipeline, and never doubles up.

Built on a real `AsyncIOScheduler` over a real `SQLAlchemyJobStore` (a temp-file
engine), because the whole point of this lane is the mechanics APScheduler
enforces: the argument-free picklable target, the create-if-absent reconcile, the
misfire event, and the durable skip record. httpx's `ASGITransport` does not run
the lifespan, so the scheduler is driven directly.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from apscheduler.events import EVENT_JOB_MISSED
from apscheduler.events import JobExecutionEvent
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Run
from app.db.repositories import operations_config_repo
from app.jobs import scheduler as scheduler_module

SCHEDULED_JOB_ID = scheduler_module.SCHEDULED_JOB_ID


@pytest_asyncio.fixture
async def wired(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Point the scheduler module at the temp DB and a clean singleton."""
    scheduler_module._SKIP_TASKS.clear()
    monkeypatch.setattr(scheduler_module, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(scheduler_module, "_scheduler", None)
    yield session_factory
    scheduler_module._SKIP_TASKS.clear()


async def _run_count(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        return int(await session.scalar(select(func.count()).select_from(Run)) or 0)


async def _seed_run(
    session_factory: async_sessionmaker[AsyncSession], *, status: str
) -> int:
    async with session_factory() as session:
        run = Run(
            search_id=None,
            trigger="manual",
            status=status,
            started_at=datetime.now(UTC),
        )
        session.add(run)
        await session.commit()
        return int(run.id)


# --- the target runs the pipeline ---------------------------------------------


async def test_the_target_runs_the_pipeline(wired) -> None:
    async with wired() as session:
        before = int(await session.scalar(select(func.count()).select_from(Run)) or 0)
    assert before == 0

    result = await scheduler_module.run_scheduled_pipeline()

    assert result is not None
    async with wired() as session:
        rows = (await session.execute(select(Run))).scalars().all()
    assert len(rows) == 1, [row.id for row in rows]
    assert rows[0].trigger == "schedule"
    assert rows[0].search_id is None


# --- the in-flight guard -------------------------------------------------------


async def test_in_flight_run_is_skipped_not_overlapped(wired) -> None:
    in_flight_id = await _seed_run(wired, status="running")

    result = await scheduler_module.run_scheduled_pipeline()

    assert result is None
    # No second run row was created — the in-flight run is the only one.
    assert await _run_count(wired) == 1

    async with wired() as session:
        notice = await operations_config_repo.read_skip_notice(session)
    assert notice is not None
    assert notice["reason"] == "in_flight"
    assert notice["run_id"] == in_flight_id


# --- the missed fire is surfaced ----------------------------------------------


async def test_a_missed_fire_is_surfaced(wired) -> None:
    fired_at = datetime.now(UTC) - timedelta(hours=5)
    event = JobExecutionEvent(EVENT_JOB_MISSED, SCHEDULED_JOB_ID, "default", fired_at)

    scheduler_module._on_scheduler_event(event)
    if scheduler_module._SKIP_TASKS:
        await asyncio.gather(*scheduler_module._SKIP_TASKS)

    async with wired() as session:
        notice = await operations_config_repo.read_skip_notice(session)
    assert notice is not None
    assert notice["reason"] == "missed"
    assert notice["scheduled_for"] == fired_at.isoformat()
    # A skip never creates a run.
    assert await _run_count(wired) == 0


# --- totality ------------------------------------------------------------------


async def test_a_broken_jobstore_degrades_to_unavailable(
    wired, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom():  # noqa: ANN202 — a deliberately unbuildable jobstore
        raise RuntimeError("no engine for you")

    monkeypatch.setattr(scheduler_module, "_jobstore_engine", _boom)

    status = await scheduler_module.start_scheduler()

    assert status == "unavailable"


async def test_start_stop_are_total(wired, monkeypatch: pytest.MonkeyPatch) -> None:
    # Before any start: nothing to stop, and calling it twice is fine.
    await scheduler_module.stop_scheduler()
    await scheduler_module.stop_scheduler()

    # A stopped instance is equally a no-op.
    engine = create_engine("sqlite://")
    instance = AsyncIOScheduler(
        jobstores={"default": SQLAlchemyJobStore(engine=engine)},
        timezone=ZoneInfo("Europe/Dublin"),
    )
    monkeypatch.setattr(scheduler_module, "_scheduler", instance)
    await scheduler_module.stop_scheduler()
    await scheduler_module.stop_scheduler()
    engine.dispose()


# --- the stale-run reconciliation ---------------------------------------------


async def test_stale_running_rows_are_reconciled_to_partial(wired) -> None:
    run_id = await _seed_run(wired, status="running")

    reconciled = await scheduler_module.reconcile_stale_runs(wired)

    assert reconciled == 1
    async with wired() as session:
        row = await session.get(Run, run_id)
    assert row is not None
    assert row.status == "partial"
    assert row.finished_at is not None
    assert row.errors_json
    assert "reconciled" in row.errors_json[0]["error"]
