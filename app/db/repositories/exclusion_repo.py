"""Exclusion repository — the write side of "why is this NOT in my queue?".

One `listing_exclusions` row per **firing rule per listing per run** (D-36). The
table is append-only by contract: this module only ever INSERTs, never updates and
never deletes, so retuning a rule brings a listing back with no migration and a
past run's observations stay exactly as they were observed. One row per rule (not
one per listing) is what makes a per-rule `GROUP BY` count exact.

The evidence a row carries is `rule_id`, `rule_kind` and `detail_json` — and
`detail_json` comes straight from the pure evaluator, which is contractually
limited to terms, field names and counts. No listing prose ever reaches this table.

Every function takes `session: AsyncSession` first, never commits, and flushes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ListingExclusion
from app.domain.filter import RuleOutcome


@dataclass(frozen=True)
class ExclusionRecord:
    """One persisted rejection, as a pure value (the queue view reads this shape)."""

    listing_id: int
    run_id: int | None
    rule_id: str | None
    rule_kind: str | None
    detail: Mapping[str, Any] | None
    criteria_version: int | None
    created_at: datetime


async def record_exclusions(
    session: AsyncSession,
    *,
    listing_id: int,
    run_id: int | None,
    outcomes: Sequence[RuleOutcome],
    criteria_version: int | None = None,
    now: datetime,
    version_by_rule: Mapping[str, int | None] | None = None,
) -> int:
    """Write one row per firing outcome. Returns the rows written.

    `criteria_version` stamps **every** row with one value, which is right when a
    batch belongs to a single search. When a listing can be rejected by rules from
    several searches in the same run (the A4 union scope), pass `version_by_rule`
    — a `rule_id -> criteria_version` mapping — and each row is stamped with its
    **own** owning search's version, so the stored per-row evidence is per-row
    correct. `version_by_rule` takes precedence when supplied; a rule absent from
    the mapping records `None` rather than inheriting an unrelated search's value.

    The whole batch is wrapped in a SAVEPOINT as `source_repo` does, so one bad row
    cannot poison the run's outer transaction. `cancel` is never called: nothing is
    ever updated or deleted here (D-36, append-only per-run observations).
    """
    if not outcomes:
        return 0

    rows = [
        ListingExclusion(
            listing_id=listing_id,
            run_id=run_id,
            rule_id=outcome.rule_id,
            rule_kind=outcome.rule_kind,
            detail_json=dict(outcome.detail or {}),
            criteria_version=_criteria_version_for(
                criteria_version, version_by_rule, outcome.rule_id
            ),
            created_at=now,
        )
        for outcome in outcomes
    ]

    async with session.begin_nested():
        session.add_all(rows)
        await session.flush()

    return len(rows)


def _criteria_version_for(
    criteria_version: int | None,
    version_by_rule: Mapping[str, int | None] | None,
    rule_id: str | None,
) -> int | None:
    """One row's `criteria_version`: the per-rule override when given, else the batch value."""
    if version_by_rule is None:
        return criteria_version
    return version_by_rule.get(rule_id) if rule_id is not None else None


async def excluded_counts_for_run(session: AsyncSession, *, run_id: int) -> dict[str, int]:
    """Per-rule firing counts for one run, ordered deterministically by `rule_id`.

    The ordering makes the persisted JSON byte-stable between identical runs, which
    is what lets a reason be compared across runs at all.
    """
    rows = (
        await session.execute(
            select(ListingExclusion.rule_id, func.count())
            .where(ListingExclusion.run_id == run_id)
            .group_by(ListingExclusion.rule_id)
            .order_by(ListingExclusion.rule_id)
        )
    ).all()

    return {str(rule_id): int(count) for rule_id, count in rows if rule_id is not None}


async def rule_counts_for_listings(session: AsyncSession, *, run_id: int) -> dict[int, list[str]]:
    """The firing rule ids per listing for one run — the queue's excluded toggle.

    The SQL lives here, not in a route: plan 02-07's `Show excluded` toggle renders
    a chip per firing rule, and a route that rebuilt this query would be a second
    place for the ordering to drift.
    """
    rows = (
        await session.execute(
            select(ListingExclusion.listing_id, ListingExclusion.rule_id)
            .where(ListingExclusion.run_id == run_id)
            .order_by(ListingExclusion.listing_id, ListingExclusion.rule_id)
        )
    ).all()

    counts: dict[int, list[str]] = {}
    for listing_id, rule_id in rows:
        if rule_id is None:
            continue
        counts.setdefault(int(listing_id), []).append(str(rule_id))
    return counts


async def exclusions_for_run(session: AsyncSession, *, run_id: int) -> list[ExclusionRecord]:
    """Every exclusion this run recorded, ordered by `(listing_id, rule_id)`."""
    rows = (
        (
            await session.execute(
                select(ListingExclusion)
                .where(ListingExclusion.run_id == run_id)
                .order_by(ListingExclusion.listing_id, ListingExclusion.rule_id)
            )
        )
        .scalars()
        .all()
    )

    return [
        ExclusionRecord(
            listing_id=int(row.listing_id),
            run_id=row.run_id,
            rule_id=row.rule_id,
            rule_kind=row.rule_kind,
            detail=row.detail_json,
            criteria_version=row.criteria_version,
            created_at=row.created_at,
        )
        for row in rows
    ]


__all__ = [
    "ExclusionRecord",
    "excluded_counts_for_run",
    "exclusions_for_run",
    "record_exclusions",
    "rule_counts_for_listings",
]
