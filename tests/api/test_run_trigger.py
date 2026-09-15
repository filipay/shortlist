"""RUN-01 — the manual trigger answers immediately and creates a `runs` row."""

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

#: A gate the test can hold open so the run stays observably "running".
FETCH_GATE: dict[str, asyncio.Event] = {}


class GatedLinkedIn(JobSource):
    """A registrable LinkedIn adapter whose fetch blocks until the test releases it."""

    name = "linkedin"
    capabilities = CAPABILITIES

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        gate = FETCH_GATE.get("fetch")
        if gate is not None:
            await gate.wait()
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
    session_factory: async_sessionmaker[AsyncSession], run_id: int, *, timeout: float = 5.0
) -> Run:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        async with session_factory() as session:
            run = await session.get(Run, run_id)
        if run is not None and run.status in TERMINAL:
            return run
        await asyncio.sleep(0.01)
    raise AssertionError(f"run {run_id} never reached a terminal state")


@pytest.mark.usefixtures("registry_snapshot")
async def test_post_runs_returns_202_and_creates_a_running_row(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    registry.register(GatedLinkedIn)
    await _register_source(session_factory)
    gate = asyncio.Event()
    FETCH_GATE["fetch"] = gate

    try:
        response = await client.post("/runs")

        assert response.status_code == 202
        # The response IS the polling fragment, so htmx can swap it straight in.
        assert 'hx-get="/runs/' in response.text
        assert "running" in response.text

        run = await _latest_run(session_factory)
        assert run is not None
        assert run.status == "running"
        assert run.trigger == "manual"
    finally:
        gate.set()
        FETCH_GATE.pop("fetch", None)

    terminal = await _wait_for_terminal(session_factory, run.id)
    assert terminal.status == "done"
    assert terminal.finished_at is not None


async def test_queue_page_shows_the_trigger_control_and_the_count(client) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert 'hx-post="/runs"' in response.text
    assert 'id="run-status-slot"' in response.text
    assert "0 listings" in response.text
    assert "No listings yet" in response.text


async def test_status_route_404s_for_an_unknown_run(client) -> None:
    response = await client.get("/runs/9999/status")

    assert response.status_code == 404
