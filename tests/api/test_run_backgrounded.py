"""RUN-02 — the run is backgrounded, the UI stays responsive, and the poll stops."""

from __future__ import annotations

import asyncio
import time
from typing import Literal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Run, Source
from app.sources import registry
from app.sources.base import FetchBudget, FetchResult, JobSource, SearchQuery
from app.sources.linkedin import CAPABILITIES

TERMINAL = {"done", "partial", "failed"}

#: Long enough to observe the in-flight state comfortably, short enough for CI.
SLOW_DELAY_SECONDS = 1.0


class SlowLinkedIn(JobSource):
    """A board whose fetch takes a few hundred milliseconds (well, 1 s)."""

    name = "linkedin"
    capabilities = CAPABILITIES

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        await asyncio.sleep(SLOW_DELAY_SECONDS)
        return FetchResult(source=self.name, items=[], status="ok", requests_used=1)


async def _register_source(
    session_factory: async_sessionmaker[AsyncSession], name: str = "linkedin"
) -> None:
    async with session_factory() as session:
        session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _latest_run(session_factory: async_sessionmaker[AsyncSession]) -> Run | None:
    async with session_factory() as session:
        return (
            await session.execute(select(Run).order_by(Run.id.desc()))
        ).scalars().first()


async def _wait_for_terminal(
    session_factory: async_sessionmaker[AsyncSession], run_id: int, *, timeout: float = 10.0
) -> Run:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        async with session_factory() as session:
            run = await session.get(Run, run_id)
        if run is not None and run.status in TERMINAL:
            return run
        await asyncio.sleep(0.02)
    raise AssertionError(f"run {run_id} never reached a terminal state")


@pytest.mark.usefixtures("registry_snapshot")
async def test_handler_returns_before_the_pipeline_finishes(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    registry.register(SlowLinkedIn)
    await _register_source(session_factory)

    started = time.perf_counter()
    response = await client.post("/runs")
    elapsed = time.perf_counter() - started

    assert response.status_code == 202
    assert elapsed < SLOW_DELAY_SECONDS / 2, (
        f"the handler waited for the pipeline ({elapsed:.2f}s) — it must enqueue, not await"
    )

    run = await _latest_run(session_factory)
    assert run is not None
    assert run.status == "running"

    # 200 while the run is in flight — htmx keeps polling.
    in_flight = await client.get(f"/runs/{run.id}/status")
    assert in_flight.status_code == 200
    assert "running" in in_flight.text

    # /health stays responsive mid-run: the scrape is off the event loop.
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["db"] == "ok"

    terminal = await _wait_for_terminal(session_factory, run.id)
    assert terminal.status == "done"

    # 286 is htmx's documented stop-polling signal.
    stopped = await client.get(f"/runs/{run.id}/status")
    assert stopped.status_code == 286
    assert stopped.headers.get("HX-Reswap") == "outerHTML"
    assert "done" in stopped.text


async def test_health_is_boot_tolerant_without_any_backend(client) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
