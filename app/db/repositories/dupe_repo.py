"""Dupe repository — the only place the Tier-2 merge SQL lives.

**A5 divergence from `research/ARCHITECTURE.md` §8.3 (deliberate).** §8.3 says
"all `listing_sources` rows move to the surviving `listing_id`". This module does
**not** re-point them. Moving rows would make a revert a *data migration* rather
than a flag flip, and it destroys the absorber↔twin provenance the Merges audit
view needs. "Merged from N sources" is derived by joining through `listing_dupes`
instead, so every consumer of "which sources saw this job" must go through that
join (plan 02-06's Merges view and plan 02-07's queue read model do exactly that).

`listing_dupes` is **append-and-mark**: this module only ever INSERTs, so a revert
(plan 02-06) stays a flag flip (`reverted_at`) and nothing is ever lost.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Listing, ListingDupe
from app.db.repositories.listing_repo import _LISTING_FIELDS
from app.domain.dedup import CandidateFacts, MergeDecision

#: A field value counts as "blank" — and is therefore fillable — when it is
#: `None` or an empty string. The Tier-1 upsert loop treats `None` only; D-27 adds
#: the empty-string rule to the merge.
_BLANK = (None, "")


def _is_blank(value: Any) -> bool:
    return value is None or value == ""


def _candidate_facts(row: Listing) -> CandidateFacts:
    return CandidateFacts(
        listing_id=int(row.id),
        company_norm=row.company_norm,
        title_norm=row.title_norm or "",
        location_norm=row.location_norm,
        blocking_key=row.blocking_key,
        posted_at=row.posted_at,
        first_seen_at=row.first_seen_at,
    )


async def candidates_for_block(
    session: AsyncSession,
    *,
    company_norm: str,
    posted_window_days: int,
) -> list[CandidateFacts]:
    """Every active listing for one company, as pure `CandidateFacts`.

    One indexed read on `company_norm` equality — the **leading** column of
    `ix_listings_company_norm_title_norm`, so the block is index-usable. The bound
    that keeps this cheap is the company itself: the block is the number of roles
    that one company posted, not the corpus (T-02-12). A group of one is dropped
    by `candidate_merges` before any scoring happens.

    `posted_window_days` is accepted for one call shape with the stage, but the
    window is deliberately **not applied here**: it is a *pair* property ("two
    roles at one company a year apart are never compared"), and any per-block
    anchor would silently drop a genuinely matchable pair. The authoritative rule
    is `candidate_merges`' per-pair check.
    """
    rows = (
        (
            await session.execute(
                select(Listing).where(
                    Listing.company_norm == company_norm,
                    Listing.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    return [_candidate_facts(row) for row in rows]


async def reverted_pairs(
    session: AsyncSession, *, listing_ids: Iterable[int]
) -> set[tuple[int, int]]:
    """D-28 negative memory: pairs a user has already reverted, in **both** orientations.

    A revert must survive the next run, and because merges fire automatically
    (D-25) this pre-check is load-bearing. The plan-02-01 unique index covers a
    *same-orientation* re-insert only — SQLite treats NULLs as distinct and the
    index is on the ordered pair, so `(b, a)` is a different key and the reversed
    pair must be filtered here.
    """
    ids = {int(listing_id) for listing_id in (listing_ids or ())}
    if len(ids) < 2:
        return set()

    rows = (
        await session.execute(
            select(ListingDupe.listing_id, ListingDupe.dup_listing_id).where(
                ListingDupe.reverted_at.is_not(None),
                ListingDupe.listing_id.in_(ids),
                ListingDupe.dup_listing_id.in_(ids),
            )
        )
    ).all()

    pairs: set[tuple[int, int]] = set()
    for survivor_id, absorbed_id in rows:
        pairs.add((int(survivor_id), int(absorbed_id)))
        pairs.add((int(absorbed_id), int(survivor_id)))
    return pairs


async def merged_pairs(
    session: AsyncSession, *, listing_ids: Iterable[int]
) -> set[tuple[int, int]]:
    """Pairs already merged and not reverted, in **both** orientations.

    Symmetric to `reverted_pairs` and needed for the same reason: the merge is
    re-planned from scratch every run (D-36), so without this the same pair is
    proposed again on every re-run. The unique index would refuse the duplicate
    insert, but as a *per-run error* — a misleading warning recorded every day for
    a merge that is already correct. Filtering here keeps the run log honest.
    """
    ids = {int(listing_id) for listing_id in (listing_ids or ())}
    if len(ids) < 2:
        return set()

    rows = (
        await session.execute(
            select(ListingDupe.listing_id, ListingDupe.dup_listing_id).where(
                ListingDupe.reverted_at.is_(None),
                ListingDupe.listing_id.in_(ids),
                ListingDupe.dup_listing_id.in_(ids),
            )
        )
    ).all()

    pairs: set[tuple[int, int]] = set()
    for survivor_id, absorbed_id in rows:
        pairs.add((int(survivor_id), int(absorbed_id)))
        pairs.add((int(absorbed_id), int(survivor_id)))
    return pairs


async def apply_merge(
    session: AsyncSession,
    *,
    decision: MergeDecision,
    now: datetime,
    run_id: int | None = None,
) -> int:
    """Merge the twin into the survivor and audit it. Returns the new row id.

    The fill map is built by iterating `_LISTING_FIELDS` (reused from
    `listing_repo`; a second tuple would drift): a field is written only when the
    survivor's current value is blank **and** the twin's is not. For each field
    actually written, the survivor's **pre-merge** value is recorded, so a revert
    can restore exactly what the merge changed.

    Fills go through the survivor's **ORM row**, never raw SQL, so the
    `listings_au` FTS maintenance trigger fires and the search index cannot drift
    (T-02-14).

    The twin is never deleted and never deactivated: it stays an ordinary
    `listings` row, and its disappearance from the queue is a read-side predicate
    owned by plan 02-07.

    `run_id` is accepted for audit context but is not persisted —
    `listing_dupes` has no `run_id` column (0001's schema), and the run association
    is derivable from `merged_at`. The insert is wrapped in a SAVEPOINT as
    `listing_repo` does; a duplicate `(listing_id, dup_listing_id)` propagates as a
    `sqlalchemy.exc.IntegrityError` (the stage counts it and carries on).
    """
    survivor = await session.get(Listing, decision.survivor_id)
    twin = await session.get(Listing, decision.absorbed_id)
    if survivor is None or twin is None:
        raise LookupError(
            f"merge endpoints missing: survivor={decision.survivor_id} twin={decision.absorbed_id}"
        )

    snapshot: dict[str, Any] = {}
    for field in _LISTING_FIELDS:
        current = getattr(survivor, field)
        candidate = getattr(twin, field)
        if _is_blank(candidate):
            continue
        if _is_blank(current):
            snapshot[field] = current
            setattr(survivor, field, candidate)

    dupe = ListingDupe(
        listing_id=decision.survivor_id,
        dup_listing_id=decision.absorbed_id,
        method=decision.method,
        score=decision.score,
        snapshot_json=snapshot or None,
        merged_at=now,
    )
    async with session.begin_nested():
        session.add(dupe)
        await session.flush()

    return int(dupe.id)


async def count_merges_for_run(session: AsyncSession, *, run_id: int) -> int:
    """How many merges this run wrote.

    `listing_dupes` has no `run_id` column, so the run's merges are the rows whose
    `merged_at` falls at or after the run's `started_at` (the pipeline stamps every
    row it touches with the run's own clock — the same window
    `source_repo.get_source_health` uses). A run that has not started yet counts
    zero.
    """
    from app.db.models import Run  # local import keeps this module import-light

    run = await session.get(Run, run_id)
    if run is None or run.started_at is None:
        return 0

    return int(
        await session.scalar(
            select(func.count())
            .select_from(ListingDupe)
            .where(ListingDupe.merged_at.is_not(None), ListingDupe.merged_at >= run.started_at)
        )
        or 0
    )


__all__ = [
    "apply_merge",
    "candidates_for_block",
    "count_merges_for_run",
    "merged_pairs",
    "reverted_pairs",
]
