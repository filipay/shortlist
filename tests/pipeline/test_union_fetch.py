"""The global run fetches the **union of every enabled search's criteria**.

The queue's main "Run" button posts `POST /runs` with no `search_id`. Before this
change that run silently fell back to the hardcoded Phase-1 `default_query()` and
never fetched with a saved search's criteria (only its rules were unioned). These
tests pin the replacement: one fetch per enabled search, per resolved adapter,
sequentially across searches and concurrently within one, with the recorded shapes
(`runs.source_counts_json`, the `persist:<source>` stage entry, the capability
warnings) still one-entry-per-source.
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, date, datetime
from typing import Literal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Run, Search, Source
from app.domain.criteria import search_query_from
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

NOW = datetime(2026, 9, 1, tzinfo=UTC)

#: The pattern `scripts/compose-smoke.sh` reads out of a `POST /runs` response.
COMPOSE_SMOKE_RUN_ID_REGEX = r'hx-get="/runs/(\d+)/status"'

#: Filled by `RouteRecordingAdapter` when the route constructs it (no test has a
#: handle on that instance).
ROUTE_QUERIES: list[SearchQuery] = []


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


class RecordingAdapter(JobSource):
    """Records every query it is handed and returns a scripted result per keyword.

    `plan` maps `query.keywords` to `(status, [RawListing, ...])`; an unknown
    keyword is a healthy empty fetch.
    """

    def __init__(
        self,
        name: str,
        *,
        capabilities: SourceCapabilities = BASE,
        plan: dict[str, tuple[str, list[RawListing]]] | None = None,
    ) -> None:
        self.name = name  # type: ignore[assignment]
        self.capabilities = capabilities
        self.queries: list[SearchQuery] = []
        self._plan = plan or {}

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        self.queries.append(query)
        status, items = self._plan.get(query.keywords, ("ok", []))
        return FetchResult(
            source=self.name,  # type: ignore[arg-type]
            items=list(items),
            status=status,  # type: ignore[arg-type]
            requests_used=1,
        )


class RouteRecordingAdapter(JobSource):
    """A no-arg adapter the registry can construct for the real `POST /runs` route."""

    name = "linkedin"
    capabilities = BASE

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        ROUTE_QUERIES.append(query)
        return FetchResult(
            source=self.name, items=[_raw("linkedin", 1)], status="ok", requests_used=1
        )


async def _register_source(
    session_factory: async_sessionmaker[AsyncSession], name: str = "linkedin"
) -> None:
    async with session_factory() as session:
        session.add(Source(name=name, display_name=name.title()))
        await session.commit()


async def _seed_search(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str,
    criteria: dict[str, object],
) -> int:
    async with session_factory() as session:
        search = Search(
            name=name,
            enabled=True,
            criteria_json=criteria,
            version=1,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(search)
        await session.flush()
        await session.commit()
        return int(search.id)


def _persist_entries(run: Run) -> list[dict]:
    assert isinstance(run.stage_log_json, list)
    return [entry for entry in run.stage_log_json if str(entry["stage"]).startswith("persist:")]


# --- both enabled searches reach the adapter, in id order ---------------------


async def test_every_enabled_searchs_query_reaches_the_adapter_in_id_order(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The global run fetches once per enabled search, in `searches.id` order.

    The names run *against* id order ("Zulu" first, "Alpha" second) so a name-sorted
    plan would be observably different: the keys are "zulu-kw" then "alpha-kw".
    """
    await _register_source(session_factory)
    first_id = await _seed_search(
        session_factory, name="Zulu", criteria={"keywords": "zulu-kw"}
    )
    second_id = await _seed_search(
        session_factory, name="Alpha", criteria={"keywords": "alpha-kw"}
    )
    assert first_id < second_id

    adapter = RecordingAdapter("linkedin")
    await run_pipeline("manual", None, session_factory, adapters=[adapter])

    assert [query.keywords for query in adapter.queries] == ["zulu-kw", "alpha-kw"], (
        "both searches must fetch, in increasing id order (not name order)"
    )


async def test_one_enabled_search_fetches_with_its_criteria_not_the_default(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_source(session_factory)
    await _seed_search(
        session_factory, name="Dublin Python", criteria={"keywords": "python", "location": "Dublin"}
    )

    adapter = RecordingAdapter("linkedin")
    await run_pipeline("manual", None, session_factory, adapters=[adapter])

    assert len(adapter.queries) == 1
    assert adapter.queries[0] == search_query_from({"keywords": "python", "location": "Dublin"})
    assert adapter.queries[0] != default_query(), "the saved search wins over default_query()"


# --- the per-search run stays scoped ------------------------------------------


async def test_a_per_search_run_fetches_only_that_searchs_criteria(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _register_source(session_factory)
    first_id = await _seed_search(
        session_factory, name="Python One", criteria={"keywords": "python"}
    )
    await _seed_search(session_factory, name="Go Two", criteria={"keywords": "golang"})

    adapter = RecordingAdapter("linkedin")
    await run_pipeline("manual", first_id, session_factory, adapters=[adapter])

    assert len(adapter.queries) == 1
    assert adapter.queries[0].keywords == "python", (
        "a scoped run must ignore every other enabled search"
    )


# --- merging per-search fetches into one source entry -------------------------


async def test_two_searches_same_source_merge_into_one_entry_with_the_worst_status(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Three searches on one source: counters sum, status is the worst seen.

    "python" and "golang" both return the same listing (so the second is an
    update); "rust" fails. The source must appear ONCE with fetched=2,
    created=1, updated=1, requests_used=3 and status "error".
    """
    await _register_source(session_factory)
    await _seed_search(session_factory, name="Python", criteria={"keywords": "python"})
    await _seed_search(session_factory, name="Go", criteria={"keywords": "golang"})
    await _seed_search(session_factory, name="Rust", criteria={"keywords": "rust"})

    adapter = RecordingAdapter(
        "linkedin",
        plan={
            "python": ("ok", [_raw("linkedin", 1)]),
            "golang": ("ok", [_raw("linkedin", 1)]),  # same source listing id
            "rust": ("error", []),
        },
    )
    run_id = await run_pipeline("manual", None, session_factory, adapters=[adapter])

    async with session_factory() as session:
        run = await session.get(Run, run_id)
    assert run is not None

    assert set(run.source_counts_json or {}) == {"linkedin"}, "ONE entry per source"
    merged = (run.source_counts_json or {})["linkedin"]
    assert merged["status"] == "error", "ok + ok + error merges to the worst status"
    assert merged["fetched"] == 2
    assert merged["created"] == 1
    assert merged["updated"] == 1
    assert merged["requests_used"] == 3
    assert run.fetched_count == 2, "the summed listings across every fetch"
    assert (run.reason_counts_json or {})["duplicates_already_seen"] == 1

    persist = _persist_entries(run)
    assert [entry["stage"] for entry in persist] == ["persist:linkedin"], (
        "exactly one persist entry per source, not one per search"
    )
    assert persist[0]["counts"] == merged


async def test_identical_criteria_fetch_the_adapter_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Two searches with equal criteria compile to an equal frozen SearchQuery."""
    await _register_source(session_factory)
    await _seed_search(session_factory, name="One", criteria={"keywords": "python"})
    await _seed_search(session_factory, name="Two", criteria={"keywords": "python"})

    adapter = RecordingAdapter(
        "linkedin", plan={"python": ("ok", [_raw("linkedin", 1)])}
    )
    run_id = await run_pipeline("manual", None, session_factory, adapters=[adapter])

    assert len(adapter.queries) == 1, "an identical second query must be skipped"
    async with session_factory() as session:
        run = await session.get(Run, run_id)
    assert run is not None
    assert (run.source_counts_json or {})["linkedin"]["fetched"] == 1


# --- capability warnings are deduped ------------------------------------------


async def test_duplicate_capability_warnings_are_deduped_across_searches(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Two searches x two boards, all four warning the same seniority filter.

    The recorded shape is one warning per `(source, filter_name, reason)` triple —
    two here (one per board) — not four.
    """
    await _register_source(session_factory, "linkedin")
    await _register_source(session_factory, "indeed")
    no_seniority = SourceCapabilities(
        supports_salary=True,
        supports_salary_min_filter=True,
        supports_remote_flag=True,
        supports_seniority=False,
        supports_full_description_in_search=True,
        requires_second_pass_for_description=False,
        supports_offset_paging=True,
        max_results_per_query=1000,
    )
    await _seed_search(
        session_factory, name="Python", criteria={"keywords": "python", "seniority": ["senior"]}
    )
    await _seed_search(
        session_factory, name="Go", criteria={"keywords": "golang", "seniority": ["senior"]}
    )
    adapters = [
        RecordingAdapter("linkedin", capabilities=no_seniority),
        RecordingAdapter("indeed", capabilities=no_seniority),
    ]

    run_id = await run_pipeline("manual", None, session_factory, adapters=adapters)

    async with session_factory() as session:
        run = await session.get(Run, run_id)
    assert run is not None
    assert isinstance(run.stage_log_json, list)
    entry = next(e for e in run.stage_log_json if e["stage"] == "criteria_compile")
    assert entry["counts"] == {"warnings": 2}, "one warning per board, not per search"
    assert {warning["source"] for warning in entry["warnings"]} == {"linkedin", "indeed"}

    warnings = [e for e in (run.errors_json or []) if e.get("status") == "warning"]
    assert len(warnings) == 2, "the errors_json warning list is deduped too"


# --- zero configuration keeps working -----------------------------------------


@pytest.mark.usefixtures("registry_snapshot")
async def test_zero_enabled_searches_uses_default_query_once_and_still_polls(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """`POST /runs` with no searches must still run and answer with the polling body."""
    registry.register(RouteRecordingAdapter)
    ROUTE_QUERIES.clear()
    await _register_source(session_factory)

    response = await client.post("/runs")

    assert response.status_code == 202
    match = re.search(COMPOSE_SMOKE_RUN_ID_REGEX, response.text)
    assert match is not None, "the compose smoke reads the run id from the body"
    run_id = int(match.group(1))

    for _ in range(200):
        async with session_factory() as session:
            run = await session.get(Run, run_id)
        if run is not None and run.status in {"done", "partial", "failed"}:
            break
        await asyncio.sleep(0.01)

    assert ROUTE_QUERIES == [default_query()], "exactly one fetch with the Phase-1 default"


# --- determinism --------------------------------------------------------------


async def test_repeating_the_run_is_deterministic(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Same inputs -> same query order and same persist order, both runs.

    The persist order is what fixes `first_seen_at` (and so the earliest-seen
    Tier-2 survivor) when two sources return the same listing.
    """
    await _register_source(session_factory, "linkedin")
    await _register_source(session_factory, "indeed")
    await _seed_search(session_factory, name="Python", criteria={"keywords": "python"})
    await _seed_search(session_factory, name="Go", criteria={"keywords": "golang"})

    async def _one_run() -> tuple[list[str], list[str], list[str]]:
        adapters = [
            RecordingAdapter(
                "linkedin",
                plan={
                    "python": ("ok", [_raw("linkedin", 1)]),
                    "golang": ("ok", [_raw("linkedin", 1)]),
                },
            ),
            RecordingAdapter(
                "indeed",
                plan={
                    "python": ("ok", [_raw("indeed", 1)]),
                    "golang": ("ok", [_raw("indeed", 1)]),
                },
            ),
        ]
        run_id = await run_pipeline("manual", None, session_factory, adapters=adapters)
        async with session_factory() as session:
            run = await session.get(Run, run_id)
        assert run is not None
        link, ind = adapters
        return (
            [q.keywords for q in link.queries],
            [q.keywords for q in ind.queries],
            [entry["stage"] for entry in _persist_entries(run)],
        )

    first = await _one_run()
    second = await _one_run()

    assert first == second, "a repeated run must reproduce query and persist order"
    assert first == (
        ["python", "golang"],
        ["python", "golang"],
        ["persist:linkedin", "persist:indeed"],
    )
