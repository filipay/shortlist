"""FILT-01 / FILT-02 — a stored rule rejects a listing and the run records why.

End to end: two boards persist their rows, the hard-filter stage loads the enabled
search's rules, evaluates them against the persisted listings, writes one
`listing_exclusions` row per firing rule, and the run reports the count. No model
call is made anywhere on this path.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import (
    FilterRule,
    Listing,
    ListingExclusion,
    LlmCall,
    Run,
    Search,
    Source,
)
from app.pipeline.run import run_pipeline
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    RawListing,
    SearchQuery,
    SourceCapabilities,
)

CRYPTO_TERM = "crypto"
SEARCH_VERSION = 3
SALARY_FLOOR = 70000

CAPABILITIES = SourceCapabilities(
    supports_salary=False,
    supports_salary_min_filter=True,
    supports_remote_flag=True,
    supports_seniority=False,
    supports_full_description_in_search=False,
    requires_second_pass_for_description=False,
    supports_offset_paging=True,
    max_results_per_query=1000,
)


class OneListingAdapter(JobSource):
    """A total adapter returning one scripted `RawListing` for its own board."""

    capabilities = CAPABILITIES

    def __init__(self, name: str, item: RawListing) -> None:
        self.name = name  # type: ignore[assignment]
        self._item = item

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(source=self.name, items=[self._item], status="ok", requests_used=1)  # type: ignore[arg-type]


def _raw(source: str, *, title: str, company: str, description: str) -> RawListing:
    return RawListing(
        source=source,  # type: ignore[arg-type]
        source_listing_id=f"{source}-1",
        source_url=f"https://{source}.example.com/jobs/1",
        direct_url=None,
        title=title,
        company_name=company,
        location_raw="Dublin, Ireland",
        description=description,
        posted_at=date(2026, 9, 1),
        # Deliberately NO salary on either listing: the salary_floor rule must not
        # reject an unknown (A2/A3).
        salary_min=None,
        salary_max=None,
        salary_interval=None,
    )


async def _register_sources(session_factory: async_sessionmaker[AsyncSession], *names: str) -> None:
    async with session_factory() as session:
        for name in names:
            session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _seed_search(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """One enabled search carrying a keyword rule and a salary-floor rule."""
    now = datetime(2026, 9, 1, tzinfo=UTC)
    async with session_factory() as session:
        search = Search(
            name="Dublin Python",
            enabled=True,
            is_default=True,
            criteria_json={
                "keywords": "python",
                "location": "Dublin",
                "salary_floor": SALARY_FLOOR,
            },
            version=SEARCH_VERSION,
            created_at=now,
            updated_at=now,
        )
        session.add(search)
        await session.flush()
        session.add_all(
            [
                FilterRule(
                    search_id=search.id,
                    kind="exclude_keyword",
                    params_json={"terms": [CRYPTO_TERM], "fields": ["description"]},
                    enabled=True,
                    position=0,
                    created_at=now,
                    updated_at=now,
                ),
                FilterRule(
                    search_id=search.id,
                    kind="salary_floor",
                    params_json={"amount": SALARY_FLOOR, "currency": "EUR"},
                    enabled=True,
                    position=1,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await session.commit()
        return int(search.id)


async def _count(session_factory: async_sessionmaker[AsyncSession], table: type) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(table)) or 0


async def test_a_stored_rule_rejects_a_listing_and_the_run_records_why(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_sources(session_factory, "linkedin", "indeed")
    await _seed_search(session_factory)
    linkedin = OneListingAdapter(
        "linkedin",
        _raw(
            "linkedin",
            title="Backend Engineer",
            company="Acme",
            description=f"We are building a {CRYPTO_TERM} trading desk.",
        ),
    )
    indeed = OneListingAdapter(
        "indeed",
        _raw(
            "indeed",
            title="Platform Engineer",
            company="Globex",
            description="Build the deployment platform.",
        ),
    )

    run_id = await run_pipeline("manual", None, session_factory, adapters=[linkedin, indeed])

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        exclusions = (await session.execute(select(ListingExclusion))).scalars().all()
        listings = (await session.execute(select(Listing).order_by(Listing.id))).scalars().all()

    assert run is not None
    # --- exactly one rejection, with all five fields --------------------------
    assert len(exclusions) == 1
    exclusion = exclusions[0]
    assert exclusion.rule_kind == "exclude_keyword"
    assert exclusion.rule_id is not None and exclusion.rule_id.isdigit()
    assert exclusion.detail_json == {"term": CRYPTO_TERM, "field": "description", "count": 1}
    assert exclusion.run_id == run_id
    assert exclusion.criteria_version == SEARCH_VERSION

    # The exclusion is against the listing that carried the term.
    by_id = {listing.id: listing for listing in listings}
    assert by_id[exclusion.listing_id].company_norm == "acme"

    # --- the unknown salary was NOT a rejection reason (A2/A3) ----------------
    assert all(exclusion.rule_kind != "salary_floor" for exclusion in exclusions)
    assert len(exclusions) == 1, "the salary_floor rule must not fire on an unknown salary"

    # --- the run reports the exclusion, and made no model call ----------------
    assert run.filtered_count == 1
    assert await _count(session_factory, LlmCall) == 0

    # --- the exclusion evidence carries no listing prose ----------------------
    assert "trading desk" not in str(exclusion.detail_json)


async def test_two_identical_runs_append_one_exclusion_row_each(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """D-36: per-run observations, append-only — never an update of the prior row."""
    await _register_sources(session_factory, "linkedin", "indeed")
    await _seed_search(session_factory)
    linkedin = OneListingAdapter(
        "linkedin",
        _raw(
            "linkedin",
            title="Backend Engineer",
            company="Acme",
            description=f"We are building a {CRYPTO_TERM} trading desk.",
        ),
    )
    indeed = OneListingAdapter(
        "indeed",
        _raw(
            "indeed",
            title="Platform Engineer",
            company="Globex",
            description="Build the deployment platform.",
        ),
    )

    first_run = await run_pipeline("manual", None, session_factory, adapters=[linkedin, indeed])
    second_run = await run_pipeline("manual", None, session_factory, adapters=[linkedin, indeed])

    async with session_factory() as session:
        exclusions = (
            (await session.execute(select(ListingExclusion).order_by(ListingExclusion.run_id)))
            .scalars()
            .all()
        )

    assert len(exclusions) == 2, "one exclusion row per run, never an update"
    assert [exclusion.run_id for exclusion in exclusions] == [first_run, second_run]
    assert all(exclusion.rule_kind == "exclude_keyword" for exclusion in exclusions)


async def test_no_enabled_search_means_no_filtering(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """An empty enabled-search set is not `no_sources_enabled` — the run still works."""
    await _register_sources(session_factory, "linkedin")
    linkedin = OneListingAdapter(
        "linkedin",
        _raw(
            "linkedin",
            title="Backend Engineer",
            company="Acme",
            description=f"We are building a {CRYPTO_TERM} trading desk.",
        ),
    )

    run_id = await run_pipeline("manual", None, session_factory, adapters=[linkedin])

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert run.filtered_count == 0
    assert await _count(session_factory, ListingExclusion) == 0
