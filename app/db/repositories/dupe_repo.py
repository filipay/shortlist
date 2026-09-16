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

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Listing, ListingDupe, ListingSource, Run
from app.db.repositories.listing_repo import _LISTING_FIELDS
from app.domain.dedup import CandidateFacts, MergeDecision

#: A field value counts as "blank" — and is therefore fillable — when it is
#: `None` or an empty string. The Tier-1 upsert loop treats `None` only; D-27 adds
#: the empty-string rule to the merge.
_BLANK = (None, "")

#: The bound on `list_merges`. The Merges page is a human-inspection surface, so a
#: pathological corpus must not build an unbounded payload; the newest rows are the
#: interesting ones, the ordering is stated, and the page names its window.
MERGE_LIST_LIMIT = 200

#: Snapshot fields that are free-form JSON blobs and are therefore never rendered as
#: snapshot pairs on the audit page (T-02-24: the page exposes no new free-form
#: field). `revert_merge` still restores them — this is a display rule, not a data
#: rule, and it lives here rather than in the template so both agree by construction.
UNRENDERED_SNAPSHOT_FIELDS = frozenset({"source_extras_json", "quality_signals_json"})

#: Every column name on the `Listing` mapper. A snapshot key outside this set is
#: skipped and counted by `revert_merge`, never `setattr`-ed: a snapshot written
#: against an older schema must degrade, not raise.
_LISTING_COLUMNS = frozenset(Listing.__table__.columns.keys())


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


# --- the Merges audit view (D-26 / D-29 / QUEUE-04 / QUEUE-09) --------------------


@dataclass(frozen=True)
class MergeSide:
    """One listing as the Merges page shows it — its OWN fields, never the other's.

    The twin is described by its own title/company/location/sources, not by an id:
    D-26 requires the absorbed record to be human-inspectable, because the only way
    to judge whether a merge was right is to read both listings.
    """

    id: int
    title: str
    company: str
    location: str
    url: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class MergeRecord:
    """One `listing_dupes` row, ready to render.

    `snapshot` is the survivor's pre-merge values as `(field, value)` pairs, sorted
    by field so the page is byte-stable between identical reads. It excludes the
    free-form JSON blobs in `UNRENDERED_SNAPSHOT_FIELDS`.
    """

    id: int
    method: str
    score: float | None
    merged_at: datetime | None
    reverted_at: datetime | None
    reverted_by: str | None
    survivor: MergeSide
    twin: MergeSide
    snapshot: tuple[tuple[str, Any], ...]

    @property
    def is_reverted(self) -> bool:
        return self.reverted_at is not None


@dataclass(frozen=True)
class MergeRate:
    """Merges over fetched for a **stated** window (QUEUE-09).

    The window is the latest run — the same run the queue's last-run strip names —
    and its id travels with the record so the page can state it rather than showing
    an unlabelled all-time aggregate.

    `rate` is `None` when the denominator is zero or unknown: a division by zero is
    a bug and a `0%` reading would be a lie. It is a whole-number percentage for
    display only; the two integers are always carried so the page renders them
    beside it and no float is ever persisted.
    """

    merged: int
    reverted: int
    fetched: int | None
    run_id: int | None

    @property
    def rate(self) -> int | None:
        if not self.fetched:
            return None
        return int(round(100.0 * self.merged / self.fetched))

    @property
    def window(self) -> str:
        return f"latest run (#{self.run_id})" if self.run_id is not None else "no run yet"


@dataclass(frozen=True)
class RevertResult:
    """The outcome of a revert attempt — always returned, never raised.

    `restored` and `skipped` name the snapshot fields that were written and the ones
    that were not a column on `Listing`. `skipped` is surfaced rather than swallowed
    so a stale snapshot is visible instead of silently partial (T-02-21).
    """

    status: str  # "reverted" | "already_reverted" | "not_found"
    dupe_id: int
    restored: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()

    @property
    def wrote(self) -> bool:
        return self.status == "reverted"

    @property
    def found(self) -> bool:
        return self.status != "not_found"


def _merge_side(
    listing_id: int, rows: Mapping[int, Listing], sources: Mapping[int, tuple[str, ...]]
) -> MergeSide:
    row = rows.get(listing_id)
    if row is None:  # pragma: no cover — the FK guarantees both endpoints exist
        return MergeSide(
            id=listing_id,
            title="",
            company="",
            location="",
            url="",
            sources=sources.get(listing_id, ()),
        )
    return MergeSide(
        id=listing_id,
        title=row.title or "",
        company=row.company_norm or "",
        location=row.location_raw or "",
        url=row.canonical_url or "",
        sources=sources.get(listing_id, ()),
    )


async def list_merges(
    session: AsyncSession,
    *,
    include_reverted: bool = True,
    limit: int = MERGE_LIST_LIMIT,
) -> list[MergeRecord]:
    """Every `listing_dupes` row, newest first, with both endpoints described.

    Ordered `(merged_at DESC, id DESC)`: newest first makes reverting a merge chain
    top-down the natural order, and the unique `id` is the mandatory tie-break —
    equal `merged_at` values are the norm, because one run merges several pairs on
    the same clock.

    A reverted row is deliberately still listed (it is the audit trail); passing
    `include_reverted=False` narrows to the merges currently in force.
    """
    bound = max(1, int(limit))
    statement = (
        select(ListingDupe)
        .order_by(ListingDupe.merged_at.desc(), ListingDupe.id.desc())
        .limit(bound)
    )
    if not include_reverted:
        statement = statement.where(ListingDupe.reverted_at.is_(None))

    dupes = (await session.execute(statement)).scalars().all()
    if not dupes:
        return []

    ids = {int(row.listing_id) for row in dupes} | {int(row.dup_listing_id) for row in dupes}

    listing_rows = {
        int(row.id): row
        for row in (
            await session.execute(select(Listing).where(Listing.id.in_(ids)))
        )
        .scalars()
        .all()
    }

    grouped: dict[int, list[str]] = {}
    for listing_id, source in (
        await session.execute(
            select(ListingSource.listing_id, ListingSource.source)
            .where(ListingSource.listing_id.in_(ids))
            .order_by(ListingSource.listing_id, ListingSource.source)
        )
    ).all():
        grouped.setdefault(int(listing_id), []).append(str(source))
    sources = {listing_id: tuple(names) for listing_id, names in grouped.items()}

    records: list[MergeRecord] = []
    for row in dupes:
        snapshot = row.snapshot_json if isinstance(row.snapshot_json, Mapping) else {}
        pairs = tuple(
            sorted(
                (str(field), value)
                for field, value in snapshot.items()
                if str(field) not in UNRENDERED_SNAPSHOT_FIELDS
            )
        )
        records.append(
            MergeRecord(
                id=int(row.id),
                method=str(row.method or ""),
                score=float(row.score) if row.score is not None else None,
                merged_at=row.merged_at,
                reverted_at=row.reverted_at,
                reverted_by=row.reverted_by,
                survivor=_merge_side(int(row.listing_id), listing_rows, sources),
                twin=_merge_side(int(row.dup_listing_id), listing_rows, sources),
                snapshot=pairs,
            )
        )
    return records


async def merge_rate(session: AsyncSession) -> MergeRate:
    """The merge rate over the latest run, with the reverted count beside it.

    Counts **un-reverted** merges only, so reverting a merge visibly moves the
    number; the reverted count is carried separately so the difference is legible
    rather than hidden (T-02-25).
    """
    merged = int(
        await session.scalar(
            select(func.count()).select_from(ListingDupe).where(ListingDupe.reverted_at.is_(None))
        )
        or 0
    )
    reverted = int(
        await session.scalar(
            select(func.count())
            .select_from(ListingDupe)
            .where(ListingDupe.reverted_at.is_not(None))
        )
        or 0
    )

    latest = (
        (
            await session.execute(
                select(Run).order_by(Run.started_at.desc(), Run.id.desc()).limit(1)
            )
        )
        .scalars()
        .first()
    )

    fetched: int | None = None
    run_id: int | None = None
    if latest is not None:
        run_id = int(latest.id)
        if latest.fetched_count is not None:
            fetched = int(latest.fetched_count)

    return MergeRate(merged=merged, reverted=reverted, fetched=fetched, run_id=run_id)


async def revert_merge(
    session: AsyncSession,
    *,
    dupe_id: int,
    now: datetime,
    actor: str = "local",
) -> RevertResult:
    """Undo one merge: restore the survivor and mark the audit row. Never deletes.

    **UPDATE-only on `listing_dupes`.** The row's `reverted_at` / `reverted_by` are
    set and its `snapshot_json` is read, never cleared, so the audit trail is
    permanent (T-02-21). `listing_sources` is **not** touched — the A5 divergence
    keeps every board's provenance row on its own listing, which is exactly why a
    revert is a flag flip and not a data migration.

    **The twin needs no un-hide step.** It is excluded from the queue because an
    un-reverted `listing_dupes` row covers it (plan 02-07's read-side predicate);
    setting `reverted_at` clears that row from the predicate and the twin is visible
    again. No `listing_events` row is written: that log records *user* actions, and
    a merge/revert is a system action already recorded here.

    **Chains: revert newest-first.** One survivor can absorb several twins, and each
    merge wrote its own snapshot. Every field named in *this* row's snapshot is
    restored unconditionally, so reverting out of order can drop a later merge's
    fill; the audit page lists merges newest-first to make the correct order the
    natural one. The later merge stays revertible, so an out-of-order revert is
    recoverable rather than lossy.

    `now` is supplied by the caller (the route) and stored as-is, so a test can pin
    it. Returns a `RevertResult`; an already-reverted row writes nothing.
    """
    dupe = await session.get(ListingDupe, dupe_id)
    if dupe is None:
        return RevertResult(status="not_found", dupe_id=int(dupe_id))
    if dupe.reverted_at is not None:
        return RevertResult(status="already_reverted", dupe_id=int(dupe.id))

    restored: list[str] = []
    skipped: list[str] = []

    survivor = await session.get(Listing, dupe.listing_id)
    if survivor is not None:
        snapshot = dupe.snapshot_json if isinstance(dupe.snapshot_json, Mapping) else {}
        for field, value in snapshot.items():
            name = str(field)
            if name not in _LISTING_COLUMNS:
                skipped.append(name)
                continue
            # Through the ORM row, never raw SQL, so the `listings_au` FTS
            # maintenance trigger fires and the search index cannot drift.
            setattr(survivor, name, value)
            restored.append(name)

    dupe.reverted_at = now
    dupe.reverted_by = actor
    await session.flush()

    return RevertResult(
        status="reverted",
        dupe_id=int(dupe.id),
        restored=tuple(restored),
        skipped=tuple(skipped),
    )


async def merge_summary_for_listings(
    session: AsyncSession, *, listing_ids: Iterable[int]
) -> dict[int, int]:
    """`{listing_id: un-reverted merges absorbed onto it}`, in one query.

    **Un-reverted only**: a reverted merge must stop claiming "merged from N
    sources", so this is the read model plan 02-07's queue row consumes. Ordering is
    by `listing_id` so the mapping is deterministic; the callers that need a
    per-source breakdown go through `list_merges` instead (the A5 join).
    """
    ids = {int(listing_id) for listing_id in (listing_ids or ())}
    if not ids:
        return {}

    rows = (
        await session.execute(
            select(ListingDupe.listing_id, func.count())
            .where(
                ListingDupe.listing_id.in_(ids),
                ListingDupe.reverted_at.is_(None),
            )
            .group_by(ListingDupe.listing_id)
            .order_by(ListingDupe.listing_id)
        )
    ).all()

    return {int(listing_id): int(count) for listing_id, count in rows}


__all__ = [
    "MERGE_LIST_LIMIT",
    "UNRENDERED_SNAPSHOT_FIELDS",
    "MergeRate",
    "MergeRecord",
    "MergeSide",
    "RevertResult",
    "apply_merge",
    "candidates_for_block",
    "count_merges_for_run",
    "list_merges",
    "merge_rate",
    "merge_summary_for_listings",
    "merged_pairs",
    "revert_merge",
    "reverted_pairs",
]
