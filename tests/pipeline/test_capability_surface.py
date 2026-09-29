"""SRC-09 / D-37 / T-02-19 — every unsupported filter is reported in two places.

The unit lane (`tests/sources/test_capabilities.py`) proves the *compiler* warns.
This lane proves the warning survives to the run boundary: it stays in
`runs.errors_json` in the pre-existing shape **and** lands in `runs.stage_log_json`
under `criteria_compile` as a structured `source`/`filter_name`/`reason` triple, so
the run detail page can render it its own way without parsing the error list.

That is the difference between "reported rather than silently ignored" and a warning
that only exists in one place a future UI might stop reading. The persisted sentence
is now exact: a board's missing seniority filter is enforced locally from the
search's own seniority criterion, while any other unsupported fetch-side filter is
only enforced locally when the search also has a matching exclusion rule.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import FilterRule, Run, Search, Source
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

SALARY_FLOOR = 70000

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


class NoSalaryFilterAdapter(JobSource):
    """A board that cannot filter on a salary minimum."""

    name = "linkedin"
    capabilities = replace(BASE, supports_salary_min_filter=False)

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(source=self.name, items=[_raw("linkedin")], status="ok", requests_used=1)


class NoRemoteFilterAdapter(JobSource):
    """A board that cannot filter on a remote flag."""

    name = "linkedin"
    capabilities = replace(BASE, supports_remote_flag=False)

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(source=self.name, items=[_raw("linkedin")], status="ok", requests_used=1)


class NoSeniorityFilterAdapter(JobSource):
    """A board that cannot filter on seniority (both real adapters' shape)."""

    name = "linkedin"
    capabilities = replace(BASE, supports_seniority=False)

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(source=self.name, items=[_raw("linkedin")], status="ok", requests_used=1)


def _raw(source: str) -> RawListing:
    return RawListing(
        source=source,  # type: ignore[arg-type]
        source_listing_id=f"{source}-1",
        source_url=f"https://{source}.example.com/jobs/1",
        direct_url=None,
        title="Backend Engineer",
        company_name="Acme",
        location_raw="Dublin, Ireland",
        description="Build the thing.",
        posted_at=date(2026, 9, 1),
    )


async def _seed_source_row(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """A `sources` row, so the persisted listing's FK resolves."""
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        await session.commit()


async def _seed_search(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    criteria: dict[str, object],
    rule_kind: str,
    rule_params: dict[str, object],
) -> int:
    now = datetime(2026, 9, 1, tzinfo=UTC)
    async with session_factory() as session:
        search = Search(
            name="Dublin Python",
            enabled=True,
            criteria_json=criteria,
            version=4,
            created_at=now,
            updated_at=now,
        )
        session.add(search)
        await session.flush()
        session.add(
            FilterRule(
                search_id=search.id,
                kind=rule_kind,
                params_json=rule_params,
                enabled=True,
                position=0,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
        return int(search.id)


def _criteria_compile_entry(run: Run) -> dict:
    assert isinstance(run.stage_log_json, list)
    matches = [entry for entry in run.stage_log_json if entry["stage"] == "criteria_compile"]
    assert len(matches) == 1, "a run always records exactly one criteria_compile entry"
    return matches[0]


@pytest.mark.usefixtures("registry_snapshot")
async def test_an_unsupported_salary_floor_is_warned_in_both_places(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry.register(NoSalaryFilterAdapter)
    await _seed_source_row(session_factory)
    await _seed_search(
        session_factory,
        criteria={"keywords": "python", "salary_floor": SALARY_FLOOR},
        rule_kind="salary_floor",
        rule_params={"amount": SALARY_FLOOR, "currency": "EUR"},
    )

    run_id = await run_pipeline(
        "manual",
        None,
        session_factory,
        query=SearchQuery(keywords="python", salary_floor=SALARY_FLOOR),
    )

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert run.status != "failed", "a capability warning degrades nothing by itself"

    # (a) The pre-existing warning shape is untouched: a warning record in
    # `errors_json`, not a run failure. Phase-1 assertions on this text still hold
    # because the sentence is EXTENDED, never replaced.
    warnings = [entry for entry in (run.errors_json or []) if entry.get("status") == "warning"]
    assert len(warnings) == 1
    assert warnings[0]["source"] == "linkedin"
    assert "filter not applied: salary_floor" in warnings[0]["error"]
    # salary_floor has no implicit local rule: do not claim it is enforced locally.
    assert "not enforced locally unless" in warnings[0]["error"]
    assert "enforced locally as a hard filter after the fetch" not in warnings[0]["error"]

    # (b) The same warning reaches the stage log as a structured triple.
    entry = _criteria_compile_entry(run)
    assert entry["counts"] == {"warnings": 1}
    assert entry["warnings"] == [
        {
            "source": "linkedin",
            "filter_name": "salary_floor",
            "reason": "the board has no salary-minimum filter",
        }
    ]
    # Plain values only: the stage log round-trips through JSON unchanged.
    assert json.loads(json.dumps(run.stage_log_json)) == run.stage_log_json


@pytest.mark.usefixtures("registry_snapshot")
async def test_an_unsupported_remote_filter_is_warned_in_both_places(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry.register(NoRemoteFilterAdapter)
    await _seed_source_row(session_factory)
    await _seed_search(
        session_factory,
        criteria={"keywords": "python", "remote_only": True},
        rule_kind="remote",
        rule_params={"require": True},
    )

    run_id = await run_pipeline(
        "manual",
        None,
        session_factory,
        query=SearchQuery(keywords="python", remote_only=True),
    )

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert run.status != "failed"

    warnings = [entry for entry in (run.errors_json or []) if entry.get("status") == "warning"]
    assert len(warnings) == 1
    assert warnings[0]["source"] == "linkedin"
    assert "filter not applied: remote_only" in warnings[0]["error"]
    assert "not enforced locally unless" in warnings[0]["error"]

    entry = _criteria_compile_entry(run)
    assert entry["counts"] == {"warnings": 1}
    assert entry["warnings"] == [
        {
            "source": "linkedin",
            "filter_name": "remote_only",
            "reason": "the board has no remote filter",
        }
    ]


@pytest.mark.usefixtures("registry_snapshot")
async def test_a_board_that_honours_every_filter_records_an_empty_warning_list(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The entry is unconditional — an empty list is honest, a missing entry is not."""
    registry.register(NoSalaryFilterAdapter)
    await _seed_source_row(session_factory)

    run_id = await run_pipeline(
        "manual",
        None,
        session_factory,
        query=SearchQuery(keywords="python"),
    )

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    assert not [e for e in (run.errors_json or []) if e.get("status") == "warning"]
    entry = _criteria_compile_entry(run)
    assert entry["counts"] == {"warnings": 0}
    assert entry["warnings"] == []


@pytest.mark.usefixtures("registry_snapshot")
async def test_an_unsupported_seniority_filter_is_enforced_locally(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The board cannot filter on seniority, but the criterion IS enforced locally."""
    registry.register(NoSeniorityFilterAdapter)
    await _seed_source_row(session_factory)

    run_id = await run_pipeline(
        "manual",
        None,
        session_factory,
        query=SearchQuery(keywords="python", seniority=("junior", "graduate")),
    )

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    warnings = [entry for entry in (run.errors_json or []) if entry.get("status") == "warning"]
    assert len(warnings) == 1
    assert "filter not applied: seniority" in warnings[0]["error"]
    assert (
        "enforced locally after the fetch from the search's own seniority criterion"
        in warnings[0]["error"]
    )


def test_no_copy_promises_local_enforcement_of_an_unenforced_criterion() -> None:
    """The criteria page must not claim every missing board filter is enforced locally."""
    template = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "web"
        / "templates"
        / "html"
        / "criteria.html"
    ).read_text(encoding="utf-8")

    assert "will still be enforced locally" not in template
    assert "enforced locally after the fetch from your seniority criterion" in template
    assert "not enforced locally unless this search also has a matching exclusion rule" in template
