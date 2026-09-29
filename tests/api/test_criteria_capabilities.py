"""SRC-09 / D-37 / T-02-32 — a filter a board cannot honour is reported before any run.

The criteria page compiles every enabled search against every enabled adapter's
declared capabilities and renders the structured `CapabilityWarning` triples, each
naming the board and the filter. The rendered sentence is exact about local
enforcement: seniority is enforced locally from the search's own criterion; any
other unsupported fetch-side filter is not enforced locally unless the search also
has a matching exclusion rule. A registry failure degrades to no warnings, never a
500.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Literal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Search, Source
from app.sources import registry
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    SearchQuery,
    SourceCapabilities,
)

BASE = SourceCapabilities(
    supports_salary=True,
    supports_salary_min_filter=True,
    supports_remote_flag=True,
    supports_seniority=True,
    supports_full_description_in_search=True,
    requires_second_pass_for_description=False,
    supports_offset_paging=True,
    max_results_per_query=1000,
)

NOT_LOCALLY_ENFORCED_SENTENCE = (
    "not enforced locally unless this search also has a matching exclusion rule"
)
SENIORITY_LOCAL_ENFORCEMENT_SENTENCE = (
    "enforced locally after the fetch from your seniority criterion"
)


class _BaseAdapter(JobSource):
    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(source=self.name, items=[], status="ok", requests_used=1)


class NoSalaryAdapter(_BaseAdapter):
    name = "linkedin"
    capabilities = replace(BASE, supports_salary_min_filter=False)


class NoRemoteAdapter(_BaseAdapter):
    name = "indeed"
    capabilities = replace(BASE, supports_remote_flag=False)


class FullyCapableAdapter(_BaseAdapter):
    name = "linkedin"
    capabilities = BASE


class NoSeniorityAdapter(_BaseAdapter):
    name = "indeed"
    capabilities = replace(BASE, supports_seniority=False)


async def _seed_source_rows(
    session_factory: async_sessionmaker[AsyncSession], *names: str
) -> None:
    async with session_factory() as session:
        for name in names:
            session.add(Source(name=name, display_name=name.title(), enabled=True))
        await session.commit()


async def _seed_search(
    session_factory: async_sessionmaker[AsyncSession], criteria: dict[str, object]
) -> int:
    now = datetime(2026, 9, 1, tzinfo=UTC)
    async with session_factory() as session:
        search = Search(
            name="Dublin Python",
            enabled=True,
            criteria_json=criteria,
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(search)
        await session.commit()
        return int(search.id)


@pytest.mark.usefixtures("registry_snapshot")
async def test_an_unsupported_filter_is_reported_per_board(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    registry.register(NoSalaryAdapter)
    registry.register(NoRemoteAdapter)
    await _seed_source_rows(session_factory, "linkedin", "indeed")
    await _seed_search(
        session_factory,
        {"keywords": "python", "salary_floor": 70000, "remote_only": True},
    )

    response = await client.get("/searches")

    assert response.status_code == 200
    assert 'class="capability-warnings"' in response.text
    # Both boards and both filters are named.
    assert "<strong>linkedin</strong>" in response.text
    assert "<code>salary_floor</code>" in response.text
    assert "the board has no salary-minimum filter" in response.text
    assert "<strong>indeed</strong>" in response.text
    assert "<code>remote_only</code>" in response.text
    assert "the board has no remote filter" in response.text
    # The message is honest, not alarming: salary_floor/remote_only have no implicit
    # local rule, so the page does not claim they are enforced locally.
    assert NOT_LOCALLY_ENFORCED_SENTENCE in response.text


@pytest.mark.usefixtures("registry_snapshot")
async def test_an_unsupported_seniority_filter_is_enforced_locally(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The board cannot filter on seniority, but the criterion is enforced locally."""
    registry.register(NoSeniorityAdapter)
    await _seed_source_rows(session_factory, "indeed")
    await _seed_search(
        session_factory,
        {"keywords": "python", "seniority": ["junior", "graduate"]},
    )

    response = await client.get("/searches")

    assert response.status_code == 200
    assert "<code>seniority</code>" in response.text
    assert SENIORITY_LOCAL_ENFORCEMENT_SENTENCE in response.text
    assert NOT_LOCALLY_ENFORCED_SENTENCE not in response.text


@pytest.mark.usefixtures("registry_snapshot")
async def test_a_fully_supported_search_renders_no_warning(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    registry.register(FullyCapableAdapter)
    await _seed_source_rows(session_factory, "linkedin")
    await _seed_search(session_factory, {"keywords": "python"})

    response = await client.get("/searches")

    assert response.status_code == 200
    assert 'class="capability-warnings"' not in response.text


@pytest.mark.usefixtures("registry_snapshot")
async def test_a_registry_failure_degrades_to_no_warnings_not_a_500(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """An enabled `sources` row with no adapter class is skipped, not fatal."""
    registry.register(FullyCapableAdapter)
    await _seed_source_rows(session_factory, "linkedin", "ghost")
    await _seed_search(
        session_factory,
        {"keywords": "python", "salary_floor": 70000},
    )

    response = await client.get("/searches")

    assert response.status_code == 200
    assert 'class="capability-warnings"' not in response.text
