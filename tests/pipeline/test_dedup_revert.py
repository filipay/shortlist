"""QUEUE-04 / D-28 / T-02-22 — a reverted merge stays reverted.

The failure this lane exists to prevent is the one that makes automatic merging
unsafe: the user undoes a wrong merge, the next run silently makes it again, and the
twin vanishes for a second time with no new evidence. The control is plan 02-04's
negative-memory pre-check reading `reverted_at`; this lane proves it at the *pipeline*
boundary by driving real runs, not by calling the repository in isolation.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingDupe, Run, Source
from app.db.repositories.dupe_repo import (
    RevertResult,
    merge_summary_for_listings,
    revert_merge,
    reverted_pairs,
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

#: One job, N boards. An identical (company, title, location) tuple on every row is
#: what makes them a Tier-2 candidate block.
SAME_JOB_TITLE = "Senior Python Engineer"
SAME_JOB_COMPANY = "Acme"
SAME_JOB_LOCATION = "Dublin, Ireland"

TWIN_SALARY_MIN = 70000.0
TWIN_SALARY_MAX = 80000.0
TWIN_DESCRIPTION = "Build the thing."
SURVIVOR_DESCRIPTION = ""

REVERTED_AT = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)

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


def _raw(
    source: str,
    *,
    description: str = TWIN_DESCRIPTION,
    salary: bool = False,
) -> RawListing:
    return RawListing(
        source=source,  # type: ignore[arg-type]
        source_listing_id=f"{source}-same-job",
        source_url=f"https://{source}.example.com/jobs/same-job",
        direct_url=None,
        title=SAME_JOB_TITLE,
        company_name=SAME_JOB_COMPANY,
        location_raw=SAME_JOB_LOCATION,
        description=description,
        posted_at=date(2026, 9, 1),
        salary_min=TWIN_SALARY_MIN if salary else None,
        salary_max=TWIN_SALARY_MAX if salary else None,
        salary_interval="year" if salary else None,
        salary_currency="EUR" if salary else None,
    )


def _pair() -> list[SameJobAdapter]:
    """The survivor (first, so the earlier-seen one) and one salary-bearing twin."""
    return [
        SameJobAdapter("linkedin", _raw("linkedin")),
        SameJobAdapter("indeed", _raw("indeed", salary=True)),
    ]


async def _register_sources(
    session_factory: async_sessionmaker[AsyncSession], *names: str
) -> None:
    async with session_factory() as session:
        for name in names:
            session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _count(session_factory: async_sessionmaker[AsyncSession], table: type) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(table)) or 0


async def _listings(session_factory: async_sessionmaker[AsyncSession]) -> dict[int, Listing]:
    async with session_factory() as session:
        rows = (await session.execute(select(Listing).order_by(Listing.id))).scalars().all()
        return {int(row.id): row for row in rows}


async def _dupes(session_factory: async_sessionmaker[AsyncSession]) -> list[ListingDupe]:
    async with session_factory() as session:
        return (
            (await session.execute(select(ListingDupe).order_by(ListingDupe.id)))
            .scalars()
            .all()
        )


async def _revert(
    session_factory: async_sessionmaker[AsyncSession], dupe_id: int
) -> RevertResult:
    async with session_factory() as session:
        result = await revert_merge(session, dupe_id=dupe_id, now=REVERTED_AT)
        await session.commit()
    return result


async def _set_snapshot(
    session_factory: async_sessionmaker[AsyncSession], dupe_id: int, snapshot: object
) -> None:
    async with session_factory() as session:
        row = await session.get(ListingDupe, dupe_id)
        assert row is not None
        row.snapshot_json = snapshot
        await session.commit()


# --- merge, revert, and stay reverted -----------------------------------------


async def test_a_reverted_merge_is_durable_and_the_pair_stays_separate(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_sources(session_factory, "linkedin", "indeed")
    first_run = await run_pipeline("manual", None, session_factory, adapters=_pair())

    async with session_factory() as session:
        run = await session.get(Run, first_run)
    assert run is not None and run.deduped_count == 1

    dupes = await _dupes(session_factory)
    assert len(dupes) == 1
    dupe_id = int(dupes[0].id)
    survivor_id = int(dupes[0].listing_id)
    twin_id = int(dupes[0].dup_listing_id)

    # --- the queue-row indicator is non-zero while the merge is in force -------
    async with session_factory() as session:
        before = await merge_summary_for_listings(
            session, listing_ids=[survivor_id, twin_id]
        )
    assert before == {survivor_id: 1}

    async with session_factory() as session:
        survivor_before = await session.get(Listing, survivor_id)
    assert survivor_before is not None
    assert survivor_before.salary_min == TWIN_SALARY_MIN, "the merge filled the blank"

    # --- revert: the same function the route calls -----------------------------
    result = await _revert(session_factory, dupe_id)

    assert result.status == "reverted"
    assert result.wrote is True

    async with session_factory() as session:
        dupe = await session.get(ListingDupe, dupe_id)
        survivor = await session.get(Listing, survivor_id)
    assert dupe is not None, "the audit row is never deleted"
    assert dupe.reverted_at == REVERTED_AT.replace(tzinfo=None)
    assert dupe.reverted_by == "local"
    assert survivor is not None
    assert survivor.salary_min is None, "the snapshot value was restored"
    assert survivor.salary_max is None
    assert survivor.title == SAME_JOB_TITLE, "only snapshot fields are touched"

    # --- the pair is separated, in BOTH orientations ---------------------------
    async with session_factory() as session:
        forward = await reverted_pairs(session, listing_ids=[survivor_id, twin_id])
        backward = await reverted_pairs(session, listing_ids=[twin_id, survivor_id])
    assert forward == {(survivor_id, twin_id), (twin_id, survivor_id)}
    assert backward == forward, "a future ordering change must not reopen the merge"

    # --- the queue-row indicator disappears ------------------------------------
    async with session_factory() as session:
        after = await merge_summary_for_listings(session, listing_ids=[survivor_id, twin_id])
    assert after == {}

    # --- the decisive property: the NEXT run does not re-merge -----------------
    second_run = await run_pipeline("manual", None, session_factory, adapters=_pair())

    async with session_factory() as session:
        run_two = await session.get(Run, second_run)
    assert run_two is not None
    assert run_two.deduped_count == 0, "a reverted pair must never be merged again"
    assert await _count(session_factory, ListingDupe) == 1, "no new dupe row"

    after_run = await _listings(session_factory)
    assert after_run[survivor_id].salary_min is None, "the second run re-filled the blank"
    assert after_run[survivor_id].title == SAME_JOB_TITLE
    dedup_errors = [
        entry for entry in (run_two.errors_json or []) if entry.get("source") == "dedup"
    ]
    assert dedup_errors == [], "a reverted pair must not be recorded as a dedup error"


# --- chains -------------------------------------------------------------------


def _chain() -> list[SameJobAdapter]:
    """Three boards, one job, and two DISJOINT contributed fields.

    The survivor (first adapter) has a blank description and no salary; the second
    contributes the salary, the third the description. Disjoint fills make the revert
    ORDER observable, which is the point of the chain case.
    """
    return [
        SameJobAdapter("linkedin", _raw("linkedin", description=SURVIVOR_DESCRIPTION)),
        SameJobAdapter("indeed", _raw("indeed", description=SURVIVOR_DESCRIPTION, salary=True)),
        SameJobAdapter("adzuna", _raw("adzuna", description=TWIN_DESCRIPTION)),
    ]


async def test_a_merge_chain_reverts_newest_first_and_survives_a_third_run(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_sources(session_factory, "linkedin", "indeed", "adzuna")
    first_run = await run_pipeline("manual", None, session_factory, adapters=_chain())

    async with session_factory() as session:
        run = await session.get(Run, first_run)
    assert run is not None and run.deduped_count == 2, "a three-way duplicate is two merges"

    dupes = await _dupes(session_factory)
    assert len(dupes) == 2
    survivor_id = int(dupes[0].listing_id)
    assert {int(row.listing_id) for row in dupes} == {survivor_id}, (
        "both merges land on the earliest-seen survivor, not a chain of survivors"
    )

    listings = await _listings(session_factory)
    assert listings[survivor_id].salary_min == TWIN_SALARY_MIN
    assert listings[survivor_id].description == TWIN_DESCRIPTION

    # Newest first — exactly the order the Merges page presents.
    newest, oldest = dupes[-1], dupes[0]

    await _revert(session_factory, int(newest.id))

    listings = await _listings(session_factory)
    # The newest merge wrote the description; its restore must not touch the salary
    # the older merge wrote.
    assert listings[survivor_id].description == SURVIVOR_DESCRIPTION
    assert listings[survivor_id].salary_min == TWIN_SALARY_MIN, (
        "reverting one merge must restore only that merge's snapshot"
    )

    await _revert(session_factory, int(oldest.id))

    listings = await _listings(session_factory)
    assert listings[survivor_id].salary_min is None

    async with session_factory() as session:
        pairs = await reverted_pairs(
            session, listing_ids=list(listings)
        )
    assert len(pairs) == 4, "both pairs, both orientations: two pairs separated"

    # --- a third run re-merges neither pair ------------------------------------
    third_run = await run_pipeline("manual", None, session_factory, adapters=_chain())

    async with session_factory() as session:
        run_three = await session.get(Run, third_run)
    assert run_three is not None and run_three.deduped_count == 0
    assert await _count(session_factory, ListingDupe) == 2


# --- totality against a stale snapshot ----------------------------------------


async def test_reverting_a_null_snapshot_still_separates_the_pair(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """An absent snapshot is a no-op RESTORE, not a no-op revert (QUEUE-04 empty)."""
    await _register_sources(session_factory, "linkedin", "indeed")
    await run_pipeline("manual", None, session_factory, adapters=_pair())

    dupes = await _dupes(session_factory)
    dupe_id = int(dupes[0].id)
    survivor_id = int(dupes[0].listing_id)
    twin_id = int(dupes[0].dup_listing_id)
    await _set_snapshot(session_factory, dupe_id, None)

    result = await _revert(session_factory, dupe_id)

    assert result.status == "reverted"
    assert result.restored == ()

    async with session_factory() as session:
        dupe = await session.get(ListingDupe, dupe_id)
        pairs = await reverted_pairs(session, listing_ids=[survivor_id, twin_id])
    assert dupe is not None and dupe.reverted_at is not None
    assert pairs == {(survivor_id, twin_id), (twin_id, survivor_id)}

    second_run = await run_pipeline("manual", None, session_factory, adapters=_pair())
    async with session_factory() as session:
        run_two = await session.get(Run, second_run)
    assert run_two is not None and run_two.deduped_count == 0


async def test_a_snapshot_key_that_is_not_a_column_is_skipped_and_counted(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A snapshot written against an older schema degrades; it never raises."""
    await _register_sources(session_factory, "linkedin", "indeed")
    await run_pipeline("manual", None, session_factory, adapters=_pair())

    dupes = await _dupes(session_factory)
    dupe_id = int(dupes[0].id)
    survivor_id = int(dupes[0].listing_id)
    await _set_snapshot(
        session_factory, dupe_id, {"salary_min": None, "not_a_real_column": 42}
    )

    result = await _revert(session_factory, dupe_id)

    assert result.status == "reverted"
    assert result.restored == ("salary_min",)
    assert result.skipped == ("not_a_real_column",)

    async with session_factory() as session:
        survivor = await session.get(Listing, survivor_id)
    assert survivor is not None and survivor.salary_min is None
