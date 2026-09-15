"""SRC-05 — one board blocked, the other healthy: the run degrades, never aborts."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Listing, ListingSource, Run, Source
from app.pipeline.run import run_pipeline
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    RawListing,
    SearchQuery,
    SourceCapabilities,
)
from app.sources.linkedin import LinkedInAdapter

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


class StubAdapter(JobSource):
    """A total adapter with a scripted outcome — no network, no jobspy."""

    capabilities = CAPABILITIES

    def __init__(self, name: str, status: str, items: list[RawListing] | None = None) -> None:
        self.name = name  # type: ignore[assignment]
        self._status = status
        self._items = list(items or [])
        #: The query the adapter was actually handed (post capability compile).
        self.last_query: SearchQuery | None = None

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok" if self._status == "ok" else "degraded"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        self.last_query = query
        return FetchResult(
            source=self.name,  # type: ignore[arg-type]
            items=self._items,
            status=self._status,  # type: ignore[arg-type]
            requests_used=1,
            error=None if self._status == "ok" else "blocked by test",
        )


def _raw(source: str, index: int) -> RawListing:
    return RawListing(
        source=source,  # type: ignore[arg-type]
        source_listing_id=f"{source}-{index}",
        source_url=f"https://{source}.example.com/jobs/{index}",
        direct_url=None,
        title=f"Engineer {index}",
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
    )


async def _count(session_factory: async_sessionmaker[AsyncSession], table: type) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(table)) or 0


async def _register_sources(
    session_factory: async_sessionmaker[AsyncSession], *names: str
) -> None:
    """`listing_sources.source` is a live FK to `sources.name`, so the row must exist."""
    async with session_factory() as session:
        for name in names:
            session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def test_a_blocked_board_degrades_the_run_but_keeps_the_healthy_queue(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    healthy = StubAdapter("linkedin", "ok", [_raw("linkedin", 1), _raw("linkedin", 2)])
    blocked = StubAdapter("indeed", "blocked")
    await _register_sources(session_factory, "linkedin", "indeed")

    run_id = await run_pipeline(
        "manual", None, session_factory, adapters=[healthy, blocked]
    )

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert run.status == "partial", "a blocked board must not look like a clean success"
    assert run.finished_at is not None

    # The healthy board's items are persisted: one failure cannot empty the queue.
    assert await _count(session_factory, ListingSource) == 2
    assert await _count(session_factory, Listing) == 2

    counts = run.source_counts_json or {}
    assert counts["linkedin"]["status"] == "ok"
    assert counts["indeed"]["status"] == "blocked"
    assert counts["indeed"]["fetched"] == 0

    errors = run.errors_json or []
    assert any(entry["source"] == "indeed" for entry in errors)


async def test_no_exception_propagates_when_a_board_is_blocked(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    blocked = StubAdapter("indeed", "blocked")
    rate_limited = StubAdapter("glassdoor", "rate_limited")
    await _register_sources(session_factory, "indeed", "glassdoor")

    # The call must return normally — a source failure is data, not an exception.
    run_id = await run_pipeline(
        "manual", None, session_factory, adapters=[blocked, rate_limited]
    )

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert run.status == "partial"
    assert run.finished_at is not None
    assert isinstance(run_id, int)
    # Every source failed, yet the queue is untouched and no exception escaped.
    assert await _count(session_factory, ListingSource) == 0


async def test_a_run_that_resolved_no_sources_is_not_a_clean_success(
    session_factory: async_sessionmaker[AsyncSession],
    client,
) -> None:
    """Zero enabled sources fetched nothing — `done` would be a false success."""
    # No `sources` rows: `_resolve_adapters` resolves an empty adapter list.
    run_id = await run_pipeline("manual", None, session_factory)

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert run.status == "partial", "an empty run must not report a clean success"
    assert run.status != "done"
    assert run.finished_at is not None

    errors = run.errors_json or []
    assert any(
        entry.get("source") == "*" and "no enabled sources" in (entry.get("error") or "")
        for entry in errors
    ), "the empty run must record a machine-readable reason in errors_json"

    # The status fragment renders that reason, not the healthy-source sentence.
    fragment = (await client.get(f"/runs/{run_id}/status")).text
    assert "No sources ran" in fragment
    assert "healthy source" not in fragment


# --- CR-01: a zero-row frame must never be a clean, empty `done` run -----------

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "listings"


class _FrameTransport:
    """The JobSpy transport boundary, scripted: returns a frame's rows."""

    def __init__(self, rows: list[dict] | None = None) -> None:
        self._rows = list(rows or [])

    def budget_allows(self, budget: FetchBudget, *, source: str, requests_needed: int) -> bool:
        return True

    async def run_scrape(self, *, site: str, kwargs: dict, deadline_s: float) -> list[dict]:
        return list(self._rows)


async def test_a_zero_row_frame_is_not_a_done_run(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """CR-01: JobSpy swallows a board block into an EMPTY frame. That is not `done`.

    Reachable in production: the library catches its own 429/403 and returns an
    empty result, so a blocked board previously reported a clean, empty run.
    """
    await _register_sources(session_factory, "linkedin")
    # The REAL adapter over a transport that returns zero rows (a blocked board).
    adapter = LinkedInAdapter(transport=_FrameTransport())

    run_id = await run_pipeline("manual", None, session_factory, adapters=[adapter])

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert run.status != "done", "a zero-row frame must not be a clean success"
    assert run.status == "partial"
    assert (run.source_counts_json or {})["linkedin"]["fetched"] == 0

    errors = run.errors_json or []
    assert any(
        entry["source"] == "linkedin" and entry.get("error") for entry in errors
    ), "a zero-row frame must record a machine-readable reason"


async def test_a_fetch_with_rows_is_still_a_done_run(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The behaviour that is currently correct must stay correct."""
    await _register_sources(session_factory, "linkedin")
    rows = json.loads((FIXTURES / "linkedin_page1.json").read_text(encoding="utf-8"))
    adapter = LinkedInAdapter(transport=_FrameTransport(rows))

    run_id = await run_pipeline("manual", None, session_factory, adapters=[adapter])

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert run.status == "done"
    assert (run.source_counts_json or {})["linkedin"]["fetched"] == 2
    assert await _count(session_factory, ListingSource) == 2


# --- WR-01: a run whose every item failed to persist is not a clean success ---


async def test_a_run_whose_every_item_failed_to_persist_is_not_done(
    session_factory: async_sessionmaker[AsyncSession],
    client,
) -> None:
    """`listing_sources.source` is an FK to `sources.name`, so an adapter with no
    `sources` row has every item rejected. The run must not report `done`, and the
    per-source `failed` count must be visible in the fragment."""
    # `adzuna` is deliberately NOT registered in the `sources` table.
    adapter = StubAdapter("adzuna", "ok", [_raw("adzuna", 1)])

    run_id = await run_pipeline("manual", None, session_factory, adapters=[adapter])

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert run.status == "partial", "every item failed to persist — not a clean success"

    counts = run.source_counts_json or {}
    assert counts["adzuna"]["failed"] == 1
    assert counts["adzuna"]["created"] == 0
    assert counts["adzuna"]["fetched"] == 1

    fragment = (await client.get(f"/runs/{run_id}/status")).text
    assert "1 failed" in fragment, "the persist failure must be rendered, not hidden"


# --- WR-03: the run path consults the adapter's capabilities (R3/SRC-09) ------


async def test_a_filter_the_board_cannot_honour_is_recorded_not_dropped(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """SRC-09/T-01-18: a dropped filter must be a recorded warning, not silence."""
    await _register_sources(session_factory, "linkedin")
    adapter = StubAdapter("linkedin", "ok", [_raw("linkedin", 1)])
    query = SearchQuery(keywords="engineer", salary_floor=70000, seniority=("senior",))

    run_id = await run_pipeline(
        "manual", None, session_factory, adapters=[adapter], query=query
    )

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    # A warning is recorded, not a run failure: the fetch itself is healthy.
    assert run.status == "done"
    recorded = " ".join(entry.get("error") or "" for entry in (run.errors_json or []))
    assert "salary_floor" in recorded, "an unsupported filter must be recorded"
    assert "seniority" in recorded, "an unsupported filter must be recorded"

    # The unsupported filters are stripped from the query the adapter executes.
    assert adapter.last_query is not None
    assert adapter.last_query.salary_floor is None
    assert adapter.last_query.seniority == ()
