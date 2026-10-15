"""DEFECT-1 regression — the `sources` allow-list is seeded from the adapter registry.

Before this fix no production code inserted a `sources` row, so a freshly migrated
database had zero enabled sources and every run resolved zero adapters — fetching
nothing while still reporting a clean run. These tests fail if the seeding is
removed.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import main as main_module
from app.api import health as health_module
from app.db.models import Run, Source
from app.db.repositories.source_repo import (
    enabled_source_names,
    ensure_registered_sources,
)
from app.pipeline.run import run_pipeline
from app.sources import registry
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    RawListing,
    SearchQuery,
)
from app.sources.linkedin import CAPABILITIES


def _one_listing(source: str) -> RawListing:
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


class StubLinkedIn(JobSource):
    """A registrable LinkedIn adapter with no I/O."""

    name = "linkedin"
    capabilities = CAPABILITIES

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(
            source=self.name,
            items=[_one_listing(self.name)],
            status="ok",
            requests_used=1,
        )


class StubIndeed(JobSource):
    """A registrable Indeed adapter with no I/O."""

    name = "indeed"
    capabilities = CAPABILITIES

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(
            source=self.name,
            items=[_one_listing(self.name)],
            status="ok",
            requests_used=1,
        )


async def test_ensure_registered_sources_inserts_the_registry_and_is_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    expected = sorted(registry.all_adapters())
    assert expected == [
        "arbeitnow",
        "bayt",
        "glassdoor",
        "indeed",
        "jobicy",
        "linkedin",
        "remotive",
    ], "the registry is the code-level truth"

    async with session_factory() as session:
        inserted = await ensure_registered_sources(session)
        await session.commit()

    assert sorted(inserted) == expected

    async with session_factory() as session:
        rows = (await session.execute(select(Source))).scalars().all()
    assert sorted(row.name for row in rows) == expected
    assert all(row.enabled for row in rows), "every registered adapter is enabled"
    assert all(row.display_name for row in rows), "display_name is NOT NULL"

    # A second call inserts nothing.
    async with session_factory() as session:
        second = await ensure_registered_sources(session)
        await session.commit()
    assert second == []

    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(Source))
    assert count == len(expected)


async def test_enabled_source_names_returns_both_boards_after_seeding(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await ensure_registered_sources(session)
        await session.commit()

    async with session_factory() as session:
        names = await enabled_source_names(session)

    assert names == ["arbeitnow", "bayt", "glassdoor", "indeed", "jobicy", "linkedin", "remotive"]


async def test_startup_seeding_makes_health_report_both_boards(
    session_factory: async_sessionmaker[AsyncSession],
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real startup path seeds the rows `/health` reads."""
    monkeypatch.setattr(main_module, "async_session_maker", session_factory)

    async with main_module.lifespan(None):  # type: ignore[arg-type]
        pass

    async def _probe_stub(
        *, force: bool = False, names: Any = None, session_factory: Any = None
    ) -> dict[str, str]:
        return {"indeed": "ok", "linkedin": "ok"}

    monkeypatch.setattr(health_module, "probe_all", _probe_stub)

    body = (await client.get("/health")).json()

    assert set(body["sources"]) == {
        "arbeitnow",
        "bayt",
        "glassdoor",
        "indeed",
        "jobicy",
        "linkedin",
        "remotive",
    }
    assert all(entry["enabled"] is True for entry in body["sources"].values())


@pytest.mark.usefixtures("registry_snapshot")
async def test_run_pipeline_resolves_adapters_from_seeded_sources(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A run over the seeded rows resolves a non-empty adapter list."""
    registry.clear()
    registry.register(StubLinkedIn)
    registry.register(StubIndeed)

    async with session_factory() as session:
        await ensure_registered_sources(session)
        await session.commit()

    # No `adapters=` injection: the pipeline must resolve them from `sources`.
    run_id = await run_pipeline("manual", None, session_factory)

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert set(run.source_counts_json or {}) == {"indeed", "linkedin"}
    assert run.status == "done"
