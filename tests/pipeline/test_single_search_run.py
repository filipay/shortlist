"""D-45 / CRIT-03 — "Run this one" scopes strictly to one search without forking the pipeline.

The per-search run is the *same* `run_pipeline` callable with `search_id` set: it
snapshots exactly one search, fetches with that search's query, applies only that
search's rules, and stamps only that search's `last_run_at`. A union run
(`search_id=None`) fetches the union of every enabled search's criteria, so it stamps
every search it actually fetched; an explicit `query` and the zero-enabled
`default_query()` fallback are not attributable to a search and stamp nothing.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Literal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import FilterRule, ListingExclusion, Run, Search, Source
from app.pipeline.run import default_query, run_pipeline
from app.sources import registry
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    RawListing,
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

#: A listing the second search's `exclude_keyword` rule would remove if it applied.
EXCLUDABLE_TITLE = "Backend Engineer"


def _raw() -> RawListing:
    return RawListing(
        source="linkedin",  # type: ignore[arg-type]
        source_listing_id="linkedin-1",
        source_url="https://linkedin.example.com/jobs/1",
        direct_url=None,
        title=EXCLUDABLE_TITLE,
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
    )


class CapturingAdapter(JobSource):
    """Records the query it was handed, so the scoping is observable."""

    name = "linkedin"
    capabilities = BASE

    def __init__(self) -> None:
        self.queries: list[SearchQuery] = []

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        self.queries.append(query)
        return FetchResult(source=self.name, items=[_raw()], status="ok", requests_used=1)


class QuickAdapter(JobSource):
    """A no-arg registrable adapter for the API route, where the registry constructs it."""

    name = "linkedin"
    capabilities = BASE

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(source=self.name, items=[_raw()], status="ok", requests_used=1)


async def _seed_searches(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[int, int]:
    """Two enabled searches; the second carries a rule that would exclude the listing."""
    now = datetime(2026, 9, 1, tzinfo=UTC)
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        await session.flush()
        first = Search(
            name="Python One",
            enabled=True,
            criteria_json={"keywords": "python"},
            version=1,
            created_at=now,
            updated_at=now,
        )
        second = Search(
            name="Go With A Rule",
            enabled=True,
            criteria_json={"keywords": "golang"},
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add_all([first, second])
        await session.flush()
        session.add(
            FilterRule(
                search_id=second.id,
                kind="exclude_keyword",
                params_json={"terms": ["engineer"]},
                enabled=True,
                position=0,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
        return int(first.id), int(second.id)


async def test_a_single_search_run_scopes_query_snapshot_and_rules(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first_id, second_id = await _seed_searches(session_factory)
    adapter = CapturingAdapter()

    run_id = await run_pipeline(
        "manual", first_id, session_factory, adapters=[adapter]
    )

    assert len(adapter.queries) == 1
    assert adapter.queries[0].keywords == "python", "the fetch uses that search's query"

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        exclusions = await session.scalar(
            select(func.count()).select_from(ListingExclusion)
        )

    assert run is not None
    snapshot = run.criteria_snapshot_json
    assert isinstance(snapshot, dict)
    assert set(snapshot) == {str(first_id)}, "exactly one search in the snapshot"
    assert snapshot[str(first_id)]["query"]["keywords"] == "python"
    assert run.search_id == first_id

    assert exclusions == 0, "the other search's rule must not apply to this run"

    # The other search was neither run nor touched.
    async with session_factory() as session:
        first = await session.get(Search, first_id)
        second = await session.get(Search, second_id)
    assert first is not None and second is not None
    assert first.last_run_at is not None
    assert second.last_run_at is None


async def test_the_union_run_still_unions_every_enabled_search(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first_id, second_id = await _seed_searches(session_factory)
    adapter = CapturingAdapter()

    run_id = await run_pipeline("manual", None, session_factory, adapters=[adapter])

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        exclusions = await session.scalar(
            select(func.count()).select_from(ListingExclusion)
        )

    assert run is not None
    snapshot = run.criteria_snapshot_json
    assert isinstance(snapshot, dict)
    assert set(snapshot) == {str(first_id), str(second_id)}, "the union is unchanged"
    assert exclusions == 1, "in the union, the second search's rule does apply"

    # Deliberate relabel: this used to assert that a union run stamps NO search,
    # because it fetched the hardcoded `default_query()`. A union run now fetches
    # both searches' criteria, so both record their freshness.
    async with session_factory() as session:
        first = await session.get(Search, first_id)
        second = await session.get(Search, second_id)
    assert first is not None and second is not None
    assert first.last_run_at is not None
    assert second.last_run_at is not None


async def test_a_union_run_stamps_every_search_it_fetched(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Each enabled search the global run fetched is fresh on `/searches`."""
    first_id, second_id = await _seed_searches(session_factory)
    adapter = CapturingAdapter()

    await run_pipeline("manual", None, session_factory, adapters=[adapter])

    async with session_factory() as session:
        first = await session.get(Search, first_id)
        second = await session.get(Search, second_id)

    assert first is not None and second is not None
    assert first.last_run_at is not None
    assert second.last_run_at is not None
    assert first.last_run_at == second.last_run_at, "one run records one timestamp"


async def test_a_union_run_with_no_enabled_searches_stamps_nothing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A run that falls back to `default_query()` belongs to no saved search."""
    now = datetime(2026, 9, 1, tzinfo=UTC)
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        disabled = Search(
            name="Disabled",
            enabled=False,
            criteria_json={"keywords": "python"},
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(disabled)
        await session.commit()
        disabled_id = int(disabled.id)

    adapter = CapturingAdapter()
    run_id = await run_pipeline("manual", None, session_factory, adapters=[adapter])

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        row = await session.get(Search, disabled_id)

    assert run is not None
    assert run.status in {"done", "partial"}, "a zero-enabled run still succeeds"
    assert adapter.queries[0] == default_query(), "the Phase-1 fallback was used"
    assert row is not None
    assert row.last_run_at is None, "a search that was not fetched must not be stamped"


async def test_an_explicit_query_run_stamps_no_search(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """An injected query is not attributable to a saved search, even when one exists."""
    first_id, second_id = await _seed_searches(session_factory)
    adapter = CapturingAdapter()
    explicit = SearchQuery(keywords="explicit-query")

    await run_pipeline("manual", None, session_factory, adapters=[adapter], query=explicit)

    async with session_factory() as session:
        first = await session.get(Search, first_id)
        second = await session.get(Search, second_id)

    assert first is not None and second is not None
    assert first.last_run_at is None
    assert second.last_run_at is None
    assert adapter.queries == [explicit]


#: The exact pattern `scripts/compose-smoke.sh` reads out of a run response.
COMPOSE_SMOKE_RUN_ID_REGEX = r'hx-get="/runs/(\d+)/status"'


@pytest.mark.usefixtures("registry_snapshot")
async def test_post_search_run_returns_202_and_creates_one_run_row(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    import asyncio

    registry.register(QuickAdapter)
    now = datetime(2026, 9, 1, tzinfo=UTC)
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        search = Search(
            name="Python One",
            enabled=True,
            criteria_json={"keywords": "python"},
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(search)
        await session.commit()
        search_id = int(search.id)

    response = await client.post(f"/searches/{search_id}/run")

    assert response.status_code == 202
    match = re.search(COMPOSE_SMOKE_RUN_ID_REGEX, response.text)
    assert match is not None, "the compose smoke could not read the run id from the body"

    async with session_factory() as session:
        runs = (
            (await session.execute(select(Run).order_by(Run.id))).scalars().all()
        )
    assert len(runs) == 1, "one trigger creates exactly one runs row"
    assert runs[0].search_id == search_id
    assert match.group(1) == str(runs[0].id)

    # Let the background task finish before the fixture drops the overrides.
    for _ in range(200):
        async with session_factory() as session:
            fresh = await session.get(Run, runs[0].id)
        if fresh is not None and fresh.status in {"done", "partial", "failed"}:
            break
        await asyncio.sleep(0.01)
