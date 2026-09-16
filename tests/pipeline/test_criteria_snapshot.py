"""CRIT-02 / D-33 — a completed run carries the exact criteria it used.

Reproducibility here is a *storage* contract, not a replay command: the run row
holds the `SearchQuery` field values and each rule's kind/params/position, and every
exclusion row carries the criteria version current at observation. A later criteria
edit must not be able to change what a completed run says it used.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import FilterRule, Run, Search, Source
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
    capabilities = CAPABILITIES

    def __init__(self, name: str, item: RawListing) -> None:
        self.name = name  # type: ignore[assignment]
        self._item = item

    async def probe(self) -> Literal["ok", "degraded", "unreachable"]:
        return "ok"

    async def fetch(self, query: SearchQuery, budget: FetchBudget) -> FetchResult:
        return FetchResult(source=self.name, items=[self._item], status="ok", requests_used=1)  # type: ignore[arg-type]


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


async def _seed_searches(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[int, int]:
    now = datetime(2026, 9, 1, tzinfo=UTC)
    async with session_factory() as session:
        first = Search(
            name="Dublin Python",
            enabled=True,
            criteria_json={"keywords": "python", "location": "Dublin"},
            version=2,
            created_at=now,
            updated_at=now,
        )
        second = Search(
            name="Remote Go",
            enabled=True,
            criteria_json={"keywords": "golang", "remote_only": True},
            version=5,
            created_at=now,
            updated_at=now,
        )
        session.add_all([first, second])
        await session.flush()
        session.add_all(
            [
                FilterRule(
                    search_id=first.id,
                    kind="exclude_keyword",
                    params_json={"terms": ["crypto"]},
                    enabled=True,
                    position=0,
                    created_at=now,
                    updated_at=now,
                ),
                FilterRule(
                    search_id=second.id,
                    kind="location",
                    params_json={"allow": ["dublin"]},
                    enabled=True,
                    position=0,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        await session.commit()
        return int(first.id), int(second.id)


async def test_the_snapshot_carries_every_enabled_search_and_its_rules(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        await session.commit()
    first_id, second_id = await _seed_searches(session_factory)
    adapter = OneListingAdapter("linkedin", _raw("linkedin"))

    run_id = await run_pipeline("manual", None, session_factory, adapters=[adapter])

    async with session_factory() as session:
        run = await session.get(Run, run_id)

    assert run is not None
    snapshot = run.criteria_snapshot_json
    assert isinstance(snapshot, dict)
    assert set(snapshot) == {str(first_id), str(second_id)}

    first = snapshot[str(first_id)]
    assert first["name"] == "Dublin Python"
    assert first["version"] == 2
    assert first["query"]["keywords"] == "python"
    assert first["query"]["location"] == "Dublin"
    assert [rule["kind"] for rule in first["rules"]] == ["exclude_keyword"]
    assert first["rules"][0]["params"] == {"terms": ["crypto"]}
    assert first["rules"][0]["position"] == 0

    second = snapshot[str(second_id)]
    assert second["version"] == 5
    assert second["query"]["remote_only"] is True
    assert [rule["kind"] for rule in second["rules"]] == ["location"]

    # Plain values only: the snapshot round-trips through JSON unchanged.
    assert json.loads(json.dumps(snapshot)) == snapshot


async def test_editing_criteria_after_a_run_leaves_that_runs_snapshot_unchanged(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session.add(Source(name="linkedin", display_name="LinkedIn"))
        await session.commit()
    first_id, _second_id = await _seed_searches(session_factory)
    adapter = OneListingAdapter("linkedin", _raw("linkedin"))

    first_run = await run_pipeline("manual", None, session_factory, adapters=[adapter])

    async with session_factory() as session:
        before = (await session.get(Run, first_run)).criteria_snapshot_json
    assert isinstance(before, dict)

    # Edit the first search's rules and drive a second run.
    now = datetime(2026, 9, 2, tzinfo=UTC)
    async with session_factory() as session:
        rules = (
            await session.execute(select(FilterRule).where(FilterRule.search_id == first_id))
        ).scalars().all()
        for rule in rules:
            rule.params_json = {"terms": ["unpaid"]}
        await session.commit()
        session.add(
            FilterRule(
                search_id=first_id,
                kind="remote",
                params_json={"require": True},
                enabled=True,
                position=1,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    second_run = await run_pipeline("manual", None, session_factory, adapters=[adapter])

    async with session_factory() as session:
        first_after = (await session.get(Run, first_run)).criteria_snapshot_json
        second_after = (await session.get(Run, second_run)).criteria_snapshot_json

    assert first_after == before, "a later edit must not rewrite a completed run's snapshot"
    assert isinstance(second_after, dict)
    assert {rule["kind"] for rule in second_after[str(first_id)]["rules"]} == {
        "exclude_keyword",
        "remote",
    }
