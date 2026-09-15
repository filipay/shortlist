"""SRC-04 / T-01-19 — adding a source is one adapter plus one registration.

The third adapter below is defined **entirely inside this test file**. If running
it required any edit to `app/pipeline/` or `app/db/`, the "pluggable adapters"
decision would have failed — so that is asserted directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingSource, Run, Source
from app.pipeline.run import run_pipeline
from app.sources import registry
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    RawListing,
    SearchQuery,
    SourceCapabilities,
)

THIRD_BOARD = "thirdboard"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

THIRD_CAPABILITIES = SourceCapabilities(
    supports_salary=True,
    supports_salary_min_filter=True,
    supports_remote_flag=True,
    supports_seniority=True,
    supports_full_description_in_search=True,
    requires_second_pass_for_description=False,
    supports_offset_paging=True,
    max_results_per_query=500,
)


class ThirdBoardAdapter(JobSource):
    """A third board. No production module references this class."""

    name: str = THIRD_BOARD  # type: ignore[assignment]
    capabilities = THIRD_CAPABILITIES

    def __init__(self, transport: object | None = None) -> None:
        self._transport = transport

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(
            source=self.name,  # type: ignore[arg-type]
            items=[
                RawListing(
                    source=self.name,  # type: ignore[arg-type]
                    source_listing_id="third-1",
                    source_url="https://third.example.com/jobs/1",
                    direct_url=None,
                    title="Third Board Role",
                    company_name="Umbrella",
                    location_raw="Dublin, Ireland",
                    description="Do the thing.",
                )
            ],
            status="ok",
            requests_used=1,
        )


async def _register_source(
    session_factory: async_sessionmaker[AsyncSession], name: str
) -> None:
    async with session_factory() as session:
        session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _count(session_factory: async_sessionmaker[AsyncSession], table: type) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(table)) or 0


@pytest.mark.usefixtures("registry_snapshot")
async def test_a_third_adapter_registers_and_runs_through_the_pipeline(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry.register(ThirdBoardAdapter)
    await _register_source(session_factory, THIRD_BOARD)

    run_id = await run_pipeline("manual", None, session_factory)

    async with session_factory() as session:
        titles = (await session.execute(select(Listing.title))).scalars().all()
        run = await session.get(Run, run_id)

    assert titles == ["Third Board Role"]
    assert await _count(session_factory, ListingSource) == 1
    assert run is not None and run.status == "done"


def test_adding_a_source_required_no_core_edit() -> None:
    core_files = sorted((PROJECT_ROOT / "app" / "pipeline").rglob("*.py")) + sorted(
        (PROJECT_ROOT / "app" / "db").rglob("*.py")
    )
    assert core_files, "the scan must not be vacuous"

    offenders = []
    for path in core_files:
        text = path.read_text(encoding="utf-8")
        if "ThirdBoardAdapter" in text or THIRD_BOARD in text:
            offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert offenders == [], f"a core module names the third adapter: {offenders}"


def test_both_real_boards_are_registered() -> None:
    from app.sources.indeed import IndeedAdapter
    from app.sources.linkedin import LinkedInAdapter

    assert registry.get("linkedin") is LinkedInAdapter
    assert registry.get("indeed") is IndeedAdapter


def test_registration_can_be_replaced_and_removed() -> None:
    class Replacement(ThirdBoardAdapter):
        pass

    registry.register(Replacement)
    assert registry.get(THIRD_BOARD) is Replacement

    registry.unregister(THIRD_BOARD)
    with pytest.raises(registry.UnknownAdapterError):
        registry.get(THIRD_BOARD)


def test_unknown_name_raises_a_clear_error() -> None:
    with pytest.raises(registry.UnknownAdapterError, match="nope"):
        registry.get("nope")


def test_all_adapters_returns_a_deterministic_name_sorted_order() -> None:
    first = list(registry.all_adapters())
    second = list(registry.all_adapters())

    assert first == sorted(first)
    assert first == second


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
