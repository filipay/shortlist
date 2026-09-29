"""CRIT-01 / FILT-01 / FILT-04 / CRIT-02 — a form rule is the rule the run applies.

The CRUD lane pins what the form *writes* (`tests/api/test_searches_crud.py`) and
the stage lane seeds `params_json` by hand (`tests/pipeline/test_filter_stage.py`).
Neither crosses the seam, and only `exclude_keyword`'s stored shape is pinned by
the CRUD lane: a drift in another kind's form field name or params key would keep
both lanes green while the user's rule silently became a no-op. These tests drive
the real seam — POST the criteria form, then run the pipeline against the same
database — and assert the run acted on what the browser stored.

No model call is made anywhere on this path.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import FilterRule, ListingExclusion, Search, Source
from app.pipeline.run import run_pipeline
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    RawListing,
    SearchQuery,
    SourceCapabilities,
)

CAPABILITIES = SourceCapabilities(
    supports_salary=True,
    supports_salary_min_filter=True,
    supports_remote_flag=True,
    supports_seniority=True,
    supports_full_description_in_search=True,
    requires_second_pass_for_description=False,
    supports_offset_paging=True,
    max_results_per_query=1000,
)


class OneListingAdapter(JobSource):
    """A total adapter that records the query it was handed and returns one listing."""

    name = "linkedin"
    capabilities = CAPABILITIES

    def __init__(self, listing: RawListing) -> None:
        self._listing = listing
        self.queries: list[SearchQuery] = []

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        self.queries.append(query)
        return FetchResult(
            source=self.name, items=[self._listing], status="ok", requests_used=1
        )


def _raw(*, title: str = "Backend Engineer", is_remote: bool | None = None) -> RawListing:
    return RawListing(
        source="linkedin",  # type: ignore[arg-type]
        source_listing_id="linkedin-1",
        source_url="https://linkedin.example.com/jobs/1",
        direct_url=None,
        title=title,
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the deployment platform.",
        is_remote=is_remote,
        posted_at=date(2026, 9, 1),
    )


async def _register_source(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        await session.commit()


async def _only_search_id(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        row = (await session.execute(select(Search))).scalar_one()
        assert isinstance(row, Search)
        return int(row.id)


async def test_a_remote_rule_created_via_the_form_excludes_the_next_run(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The remote form's stored params must be the shape `filter.evaluate` reads.

    `remote.require` is the params key the evaluator consults; the CRUD lane never
    asserts it, so a rename here would leave every existing test green while the
    user's "remote only" rule stopped firing.
    """
    await _register_source(session_factory)
    await client.post("/searches", data={"name": "Remote only", "keywords": "python"})
    search_id = await _only_search_id(session_factory)

    created = await client.post(
        f"/searches/{search_id}/rules",
        data={"kind": "remote", "remote_require": "1"},
    )
    assert created.status_code == 200

    adapter = OneListingAdapter(_raw(is_remote=False))
    run_id = await run_pipeline("manual", None, session_factory, adapters=[adapter])

    async with session_factory() as session:
        exclusions = (await session.execute(select(ListingExclusion))).scalars().all()
        rule = (await session.execute(select(FilterRule))).scalar_one()

    assert rule.params_json == {"require": True}, (
        "the form must store the params key the evaluator reads"
    )
    assert len(exclusions) == 1
    assert exclusions[0].rule_kind == "remote"
    assert exclusions[0].rule_id == str(rule.id)
    assert exclusions[0].run_id == run_id


async def test_the_search_form_criteria_reach_the_adapter_query(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """`criteria_from_form` -> `search_query_from` -> the adapter, end to end.

    The CRUD lane pins only `keywords`/`location`; the criteria lane builds its
    mapping by hand. A form key the run assembler ignores (say a renamed
    `work_mode`) would pass both. The run is scoped to the search by id — the
    real "Run this one" path — so `_resolve_fetch_queries` reads the stored criteria.
    `work_mode=remote` is the folded successor of the old `remote_only` checkbox and
    must still reach the adapter query as `remote_only=True`.
    """
    await _register_source(session_factory)
    response = await client.post(
        "/searches",
        data={
            "name": "Dublin senior python",
            "keywords": "python",
            "location": "Dublin",
            "work_mode": "remote",
            "salary_floor": "70000",
            "seniority": "senior",
        },
    )
    assert response.status_code == 200
    search_id = await _only_search_id(session_factory)

    adapter = OneListingAdapter(_raw(is_remote=True))
    await run_pipeline("manual", search_id, session_factory, adapters=[adapter])

    assert len(adapter.queries) == 1
    query = adapter.queries[0]
    assert query.keywords == "python"
    assert query.location == "Dublin"
    assert query.remote_only is True
    assert query.salary_floor == 70000
    assert query.seniority == ("senior",)
