"""Search/rule/listing read models — the read side of criteria and hard filters.

**A4 union semantics (resolved user decision).** The queue is the **union of every
enabled search**. Rules are loaded from every enabled search, and a listing removed
by **any** enabled search's rule leaves the queue. There is deliberately no column
linking a listing to the search that retrieved it: a rule is a property of the
search that owns it, and the queue is their union.

This module is the only place the criteria/rules/listing SQL lives. It maps ORM
rows into frozen records so the pure layer (`app.domain.filter`,
`app.domain.criteria`) never sees a SQLAlchemy object — the dependency runs
repository -> domain, never the reverse.

Every function takes `session: AsyncSession` first, never commits (the caller owns
the commit) and leaves the flush to the caller, matching `source_repo.py`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FilterRule, Listing, ListingDupe, Run, Search
from app.domain.filter import ListingFacts


@dataclass(frozen=True)
class SearchRecord:
    """One enabled `searches` row, as a pure value."""

    id: int
    name: str
    criteria_json: Mapping[str, Any] | None
    version: int
    is_default: bool


@dataclass(frozen=True)
class RuleRecord:
    """One enabled `filter_rules` row.

    `rule_id` is the row id rendered as a string: `listing_exclusions.rule_id` is a
    `String(64)` column, and a stable string keeps the persisted evidence
    JSON-friendly and comparable across runs.
    """

    search_id: int
    rule_id: str
    kind: str
    params_json: Mapping[str, Any] | None
    position: int

    def as_mapping(self) -> dict[str, Any]:
        """The mapping `app.domain.criteria.rule_specs_from` consumes."""
        return {
            "search_id": self.search_id,
            "rule_id": self.rule_id,
            "kind": self.kind,
            "params_json": self.params_json,
            "position": self.position,
            "enabled": True,
        }


@dataclass(frozen=True)
class ListingRecord:
    """One listing this run touched, carrying exactly the `ListingFacts` fields."""

    id: int
    title: str
    title_norm: str | None
    description: str | None
    company_norm: str | None
    location_norm: str | None
    remote_flag: bool | None
    seniority: str | None
    salary_min: float | None
    salary_max: float | None
    salary_interval: str | None
    first_seen_at: datetime
    last_seen_at: datetime

    def as_facts(self) -> ListingFacts:
        """The pure evaluator input. The ORM row never crosses this boundary."""
        return ListingFacts(
            title=self.title or "",
            title_norm=self.title_norm,
            description=self.description,
            company_norm=self.company_norm,
            location_norm=self.location_norm,
            remote_flag=self.remote_flag,
            seniority=self.seniority,
            salary_min=self.salary_min,
            salary_max=self.salary_max,
            salary_interval=self.salary_interval,
        )


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


async def enabled_searches(session: AsyncSession) -> list[SearchRecord]:
    """Every enabled `searches` row, ordered by id (the union's group order)."""
    rows = (
        (await session.execute(select(Search).where(Search.enabled.is_(True)).order_by(Search.id)))
        .scalars()
        .all()
    )
    return [
        SearchRecord(
            id=int(row.id),
            name=row.name or "",
            criteria_json=_as_mapping(row.criteria_json),
            version=int(row.version or 1),
            is_default=bool(row.is_default),
        )
        for row in rows
    ]


async def rules_for_searches(session: AsyncSession, search_ids: Iterable[int]) -> list[RuleRecord]:
    """Every enabled rule of the given searches, ordered `(search_id, position, id)`.

    The ordering is what makes the union's evaluation order deterministic: the same
    rows produce the same `RuleSpec` order on every run, so what a run recorded is
    reproducible (CRIT-02).
    """
    ids = [int(search_id) for search_id in (search_ids or ())]
    if not ids:
        return []

    rows = (
        (
            await session.execute(
                select(FilterRule)
                .where(FilterRule.search_id.in_(ids), FilterRule.enabled.is_(True))
                .order_by(FilterRule.search_id, FilterRule.position, FilterRule.id)
            )
        )
        .scalars()
        .all()
    )

    return [
        RuleRecord(
            search_id=int(row.search_id),
            rule_id=str(row.id),
            kind=row.kind or "",
            params_json=_as_mapping(row.params_json),
            position=int(row.position or 0),
        )
        for row in rows
    ]


async def active_listings(session: AsyncSession, *, run_id: int) -> list[ListingRecord]:
    """The listings this run touched, excluding absorbed twins, ordered by id.

    "Touched by this run" reuses the Phase-1 convention (`last_seen_at >=
    run.started_at`, the same window `source_repo.get_source_health` uses) rather
    than inventing a `listings.run_id` column — `listings` has no run association by
    design, and the pipeline stamps every row it touches with the run's own clock.

    An **absorbed twin** is skipped: a listing that appears as `dup_listing_id` in an
    un-reverted `listing_dupes` row is not visible in the queue, so it is not a
    candidate for its own exclusion row. Its own exclusion evidence belongs to the
    survivor's story, and plan 02-07 owns the read-side visibility predicate.
    """
    run = await session.get(Run, run_id)
    if run is None or run.started_at is None:
        return []

    absorbed = (
        (
            await session.execute(
                select(ListingDupe.dup_listing_id).where(ListingDupe.reverted_at.is_(None))
            )
        )
        .scalars()
        .all()
    )
    absorbed_ids = {int(listing_id) for listing_id in absorbed}

    rows = (
        (
            await session.execute(
                select(Listing)
                .where(
                    Listing.is_active.is_(True),
                    Listing.last_seen_at >= run.started_at,
                )
                .order_by(Listing.id)
            )
        )
        .scalars()
        .all()
    )

    return [
        ListingRecord(
            id=int(row.id),
            title=row.title or "",
            title_norm=row.title_norm,
            description=row.description,
            company_norm=row.company_norm,
            location_norm=row.location_norm,
            remote_flag=row.remote_flag,
            seniority=row.seniority,
            salary_min=row.salary_min,
            salary_max=row.salary_max,
            salary_interval=row.salary_interval,
            first_seen_at=row.first_seen_at,
            last_seen_at=row.last_seen_at,
        )
        for row in rows
        if int(row.id) not in absorbed_ids
    ]


__all__ = [
    "ListingRecord",
    "RuleRecord",
    "SearchRecord",
    "active_listings",
    "enabled_searches",
    "rules_for_searches",
]
