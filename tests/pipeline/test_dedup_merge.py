"""QUEUE-03 / D-30 — two sources, one duplicate, one audited merge.

The thinnest true end-to-end dedup: two boards return the same job, both rows are
persisted, the post-persist dedup stage scores the pair, the earlier-seen listing
absorbs the other, and the run reports the merge. This is the integration proof
that the pure gate, the repository and the stage insertion actually compose.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingDupe, ListingSource, Run, Source
from app.db.repositories.listing_repo import _LISTING_FIELDS
from app.pipeline.run import run_pipeline
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    RawListing,
    SearchQuery,
    SourceCapabilities,
)

#: One job, two boards. The normalised (company, title, location) tuple is
#: identical on both — that is what makes the pair a Tier-2 candidate.
SAME_JOB_TITLE = "Senior Python Engineer"
SAME_JOB_COMPANY = "Acme"
SAME_JOB_LOCATION = "Dublin, Ireland"
#: The twin's contribution: the survivor has no salary, the twin does.
TWIN_SALARY_MIN = 70000.0
TWIN_SALARY_MAX = 80000.0

CAPABILITIES = SourceCapabilities(
    supports_salary=False,
    supports_salary_min_filter=False,
    supports_remote_flag=True,
    supports_seniority=False,
    supports_full_description_in_search=False,
    requires_second_pass_for_description=False,
    supports_offset_paging=True,
    max_results_per_query=1000,
)


class SameJobAdapter(JobSource):
    """A total adapter returning one scripted `RawListing` for its own board."""

    capabilities = CAPABILITIES

    def __init__(self, name: str, item: RawListing) -> None:
        self.name = name  # type: ignore[assignment]
        self._item = item

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(source=self.name, items=[self._item], status="ok", requests_used=1)  # type: ignore[arg-type]


def _raw(source: str, *, with_salary: bool) -> RawListing:
    return RawListing(
        source=source,  # type: ignore[arg-type]
        source_listing_id=f"{source}-same-job",
        source_url=f"https://{source}.example.com/jobs/same-job",
        direct_url=None,
        title=SAME_JOB_TITLE,
        company_name=SAME_JOB_COMPANY,
        location_raw=SAME_JOB_LOCATION,
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
        salary_min=TWIN_SALARY_MIN if with_salary else None,
        salary_max=TWIN_SALARY_MAX if with_salary else None,
        salary_interval="year" if with_salary else None,
        salary_currency="EUR" if with_salary else None,
    )


async def _register_sources(session_factory: async_sessionmaker[AsyncSession], *names: str) -> None:
    async with session_factory() as session:
        for name in names:
            session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _count(session_factory: async_sessionmaker[AsyncSession], table: type) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(table)) or 0


async def test_two_sources_one_job_merges_once_with_an_audit_row(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_sources(session_factory, "linkedin", "indeed")
    # Order matters only for determinism: the first adapter persists first, so its
    # listing is the earlier-seen one and therefore the survivor (D-27). The
    # salary rides on the SECOND adapter, so the survivor must be filled by it.
    linkedin = SameJobAdapter("linkedin", _raw("linkedin", with_salary=False))
    indeed = SameJobAdapter("indeed", _raw("indeed", with_salary=True))

    run_id = await run_pipeline("manual", None, session_factory, adapters=[linkedin, indeed])

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        listings = (await session.execute(select(Listing).order_by(Listing.id))).scalars().all()
        dupes = (await session.execute(select(ListingDupe))).scalars().all()

    assert run is not None
    assert len(listings) == 2, "the merge never deletes the absorbed listing"
    survivor, twin = listings[0], listings[1]

    # --- exactly one audit row, naming the survivor and the absorbed twin -------
    assert len(dupes) == 1
    dupe = dupes[0]
    assert dupe.listing_id == survivor.id
    assert dupe.dup_listing_id == twin.id
    assert dupe.method == "fuzzy_tuple"
    assert dupe.merged_at is not None
    assert dupe.reverted_at is None
    assert isinstance(dupe.snapshot_json, dict)
    assert set(dupe.snapshot_json) <= set(_LISTING_FIELDS)

    # --- the twin's salary filled the survivor's blank; nothing else moved ------
    assert survivor.salary_min == TWIN_SALARY_MIN
    assert survivor.salary_max == TWIN_SALARY_MAX
    assert survivor.title == SAME_JOB_TITLE
    assert survivor.canonical_url == "https://linkedin.example.com/jobs/same-job"
    assert twin.canonical_url == "https://indeed.example.com/jobs/same-job"

    # --- the run reports the merge, not the created count -----------------------
    assert run.deduped_count == 1
    assert run.fetched_count == 2
    assert run.status == "done"


async def test_a_merge_retains_both_sources_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A5: `listing_sources` rows stay on the absorbed twin, they are not re-pointed."""
    await _register_sources(session_factory, "linkedin", "indeed")
    linkedin = SameJobAdapter("linkedin", _raw("linkedin", with_salary=False))
    indeed = SameJobAdapter("indeed", _raw("indeed", with_salary=True))

    await run_pipeline("manual", None, session_factory, adapters=[linkedin, indeed])

    async with session_factory() as session:
        sources_by_listing = {
            listing_id: source
            for listing_id, source in (
                await session.execute(select(ListingSource.listing_id, ListingSource.source))
            ).all()
        }

    assert len(sources_by_listing) == 2, "both boards' provenance rows must survive"
    assert sorted(sources_by_listing.values()) == ["indeed", "linkedin"]


async def test_a_second_run_does_not_re_merge_or_record_a_spurious_error(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """D-36 re-plans every run, so the already-merged pair must be filtered.

    Without the `merged_pairs` pre-check the pair is re-proposed, the unique index
    refuses the duplicate insert, and every re-run records a misleading dedup
    error for a merge that is already correct.
    """
    await _register_sources(session_factory, "linkedin", "indeed")
    linkedin = SameJobAdapter("linkedin", _raw("linkedin", with_salary=False))
    indeed = SameJobAdapter("indeed", _raw("indeed", with_salary=True))

    first_run = await run_pipeline("manual", None, session_factory, adapters=[linkedin, indeed])
    second_run = await run_pipeline("manual", None, session_factory, adapters=[linkedin, indeed])

    async with session_factory() as session:
        first = await session.get(Run, first_run)
        second = await session.get(Run, second_run)

    assert first is not None and first.deduped_count == 1
    assert second is not None and second.deduped_count == 0
    assert await _count(session_factory, ListingDupe) == 1
    dedup_errors = [entry for entry in (second.errors_json or []) if entry.get("source") == "dedup"]
    assert dedup_errors == [], "an already-merged pair must not be recorded as an error"


async def test_a_run_with_no_duplicate_reports_zero_merges(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The retired meaning is gone: `deduped_count` is merges, not the created count."""
    await _register_sources(session_factory, "linkedin", "indeed")
    # Different companies -> not even a candidate block, so nothing merges.
    linkedin = SameJobAdapter(
        "linkedin",
        RawListing(
            source="linkedin",
            source_listing_id="li-1",
            source_url="https://linkedin.example.com/jobs/1",
            direct_url=None,
            title="Python Engineer",
            company_name="Acme",
            location_raw="Dublin, Ireland",
            description="Build the thing.",
            posted_at=date(2026, 9, 1),
        ),
    )
    indeed = SameJobAdapter(
        "indeed",
        RawListing(
            source="indeed",
            source_listing_id="in-1",
            source_url="https://indeed.example.com/jobs/1",
            direct_url=None,
            title="Data Scientist",
            company_name="Globex",
            location_raw="Cork, Ireland",
            description="Model the thing.",
            posted_at=date(2026, 9, 1),
        ),
    )

    run_id = await run_pipeline("manual", None, session_factory, adapters=[linkedin, indeed])

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert await _count(session_factory, ListingDupe) == 0
    assert run.deduped_count == 0
    assert run.fetched_count == 2
