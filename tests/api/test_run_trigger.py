"""RUN-01 — the manual trigger answers immediately and creates a `runs` row."""

from __future__ import annotations

import asyncio
import re
import time
from datetime import date
from typing import Literal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Run, Source
from app.sources import registry
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    RawListing,
    SearchQuery,
)
from app.sources.linkedin import CAPABILITIES

TERMINAL = {"done", "partial", "failed"}

#: A gate the test can hold open so the run stays observably "running".
FETCH_GATE: dict[str, asyncio.Event] = {}


def _one_listing(source: str = "linkedin") -> RawListing:
    """A genuinely successful fetch returns at least one row (CR-01)."""
    return RawListing(
        source=source,  # type: ignore[arg-type]
        source_listing_id=f"{source}-1",
        source_url=f"https://{source}.example.com/jobs/1",
        direct_url=None,
        title="Engineer",
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
    )


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
        return FetchResult(
            source=self.name,
            items=[_one_listing()],
            status="ok",
            requests_used=1,
        )


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


#: Source of truth: scripts/compose-smoke.sh reads the run id out of the
#: `POST /runs` response body with exactly this pattern. If either side changes,
#: this test (and the smoke) must change together — that is the point of pinning it.
COMPOSE_SMOKE_RUN_ID_REGEX = r'hx-get="/runs/(\d+)/status"'


@pytest.mark.usefixtures("registry_snapshot")
async def test_post_runs_response_carries_the_id_compose_smoke_reads(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The smoke's literal regex must extract the real run id from the real body."""
    registry.register(GatedLinkedIn)
    await _register_source(session_factory)
    gate = asyncio.Event()
    FETCH_GATE["fetch"] = gate

    try:
        response = await client.post("/runs")

        assert response.status_code == 202
        match = re.search(COMPOSE_SMOKE_RUN_ID_REGEX, response.text)
        assert match is not None, (
            "compose-smoke.sh could not read a run id from the POST /runs response"
        )
        run = await _latest_run(session_factory)
        assert run is not None
        assert match.group(1) == str(run.id)
    finally:
        gate.set()
        FETCH_GATE.pop("fetch", None)

    await _wait_for_terminal(session_factory, run.id)


async def test_queue_page_shows_the_trigger_control_and_the_count(client) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert 'hx-post="/runs"' in response.text
    assert 'id="run-status-slot"' in response.text
    assert "0 listings" in response.text
    assert "No listings yet" in response.text


async def test_queue_list_listens_for_run_finished_and_reuses_filters(client) -> None:
    """The queue auto-refreshes on `run-finished`, carrying the current filters.

    Without the trigger attribute the terminal poll stops (286) and nothing ever
    re-fetches `#queue-list`, so the user must refresh by hand — the bug this pins.
    """
    response = await client.get("/")

    assert response.status_code == 200
    assert 'id="queue-list"' in response.text
    assert 'hx-get="/queue/list"' in response.text
    assert 'hx-trigger="run-finished from:body"' in response.text
    assert 'hx-target="#queue-list"' in response.text
    # The filter form id is what carries q/toggles/sort/min_score into the refresh.
    assert 'hx-include="#queue-filters"' in response.text
    assert 'id="queue-filters"' in response.text


async def test_status_route_404s_for_an_unknown_run(client) -> None:
    response = await client.get("/runs/9999/status")

    assert response.status_code == 404
