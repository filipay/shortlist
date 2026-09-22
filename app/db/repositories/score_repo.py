"""`scores` write path — the per-factor decomposition, finally written (RANK-02).

The `scores` table has existed since migration 0001 and has never been written to.
This module is its writer. House rules, as everywhere in `app/db/repositories/`:

* repositories are the **only** place SQL lives;
* they take an `AsyncSession` explicitly and **never commit** — the caller owns
  the single commit;
* the write is wrapped in a SAVEPOINT (`session.begin_nested()`) so a failure here
  cannot poison the caller's outer transaction;
* `now` is injectable so a caller (or a test) can pin the clock.

**One row per (listing, run, criteria_version)** — the existing
``uq_scores_listing_run_criteria`` unique constraint is what enforces D-101, so a
weight tweak never multiplies rows; a re-score of the same triple updates the row
in place.

**`criteria_version` is mandatory and non-NULL.** SQLite treats NULLs as distinct
in a UNIQUE index, so a NULL would silently defeat the constraint (Pitfall 5).
Because it is keyword-only but not type-enforced, `upsert_score` raises a clear
`ValueError` when it receives `None` rather than relying on the signature.

The write surface is exactly the columns `Score` declares. There is deliberately
no `agent` column on `scores` — D-12's per-call identity (including the agent) is
recorded on the `llm_calls` row for each ranking call, and adding a column here
would force an unplanned migration.

Reads are **total**: a NULL or non-mapping JSON column degrades to an empty
container rather than raising, because a page must still render.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Score
from app.domain import rubric

#: Mirrors `ck_scores_confidence_tier` (migration 0001). Validated before any SQL
#: so an unknown tier is a legible error rather than a raw `IntegrityError`.
CONFIDENCE_TIERS: frozenset[str] = frozenset({"high", "medium", "low"})


@dataclass(frozen=True)
class ScoreRecord:
    """One `scores` row, ready to render or to compute a read-time total from."""

    id: int
    listing_id: int
    run_id: int
    search_id: int | None
    criteria_version: int
    rubric_version: str | None
    backend: str | None
    provider: str | None
    model: str | None
    #: ``(factor, sub_score)`` pairs in `rubric.FACTORS` order, absent factors
    #: omitted. A stored ``0.0`` is preserved and is never conflated with absent.
    factor_scores: tuple[tuple[str, float], ...]
    total_score: float | None
    #: The audit snapshot of the weights in force when this row was written — never
    #: the sort source (D-100; the read path uses the CURRENT weights).
    weights: dict[str, float]
    confidence_tier: str | None
    rationale: str
    #: The requirement-by-requirement breakdown (RANK-06): one entry per requirement
    #: the model returned, each carrying text, a verdict and an evidencing fact id.
    requirements: tuple[dict[str, Any], ...]
    strengths: tuple[Any, ...]
    created_at: datetime


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _json_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _json_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _factor_scores(document: Any) -> tuple[tuple[str, float], ...]:
    """Stored `factor_scores_json` as ordered `(factor, value)` pairs.

    Ordered and filtered through `rubric.FACTORS`, so no key outside the six can
    appear in a read (RANK-02 ordering) and the read order is deterministic.
    """
    mapping = _json_mapping(document)
    pairs: list[tuple[str, float]] = []
    for factor in rubric.FACTORS:
        if factor not in mapping:
            continue
        value = _as_float(mapping[factor])
        if value is not None and value >= 0.0:
            pairs.append((factor, value))
    return tuple(pairs)


def _weights(document: Any) -> dict[str, float]:
    mapping = _json_mapping(document)
    return {
        factor: (float(value) if (value := _as_float(mapping.get(factor))) is not None else 0.0)
        for factor in rubric.FACTORS
    }


def _to_record(row: Score) -> ScoreRecord:
    """One ORM row as its frozen read value. The single mapping, so write and read
    cannot disagree about a field."""
    return ScoreRecord(
        id=int(row.id),
        listing_id=int(row.listing_id),
        run_id=int(row.run_id),
        search_id=int(row.search_id) if row.search_id is not None else None,
        criteria_version=int(row.criteria_version),
        rubric_version=row.rubric_version,
        backend=row.backend,
        provider=row.provider,
        model=row.model,
        factor_scores=_factor_scores(row.factor_scores_json),
        total_score=_as_float(row.total_score),
        weights=_weights(row.weights_json),
        confidence_tier=row.confidence_tier,
        rationale=row.rationale or "",
        requirements=tuple(
            dict(entry) for entry in _json_list(row.gaps_json) if isinstance(entry, Mapping)
        ),
        strengths=tuple(_json_list(row.strengths_json)),
        created_at=row.created_at,
    )


def _factor_payload(sub_scores: Mapping[str, float]) -> dict[str, float]:
    """`factor_scores_json`: one entry per factor returned, in `rubric.FACTORS` order.

    The response schema's ``-1.0`` sentinel means "no usable data" (D-85), and the
    rubric treats every negative value as absent, so only values ``>= 0.0`` are
    written. A present ``0.0`` is written as ``0.0`` and is never conflated with an
    absent factor; a response with no present factor stores the empty object ``{}``.
    """
    payload: dict[str, float] = {}
    for factor in rubric.FACTORS:
        if factor not in sub_scores:
            continue
        value = _as_float(sub_scores[factor])
        if value is not None and value >= 0.0:
            payload[factor] = value
    return payload


def _weights_payload(weights: Mapping[str, float]) -> dict[str, float]:
    return {
        factor: (
            float(value) if (value := _as_float(weights.get(factor))) is not None else 0.0
        )
        for factor in rubric.FACTORS
    }


async def upsert_score(
    session: AsyncSession,
    *,
    listing_id: int,
    run_id: int,
    criteria_version: int,
    sub_scores: Mapping[str, float],
    weights: Mapping[str, float],
    rubric_version: str,
    confidence_tier: str,
    rationale: str,
    requirements: Sequence[Mapping[str, Any]],
    total_score: float | None,
    provider: str | None,
    model: str | None,
    search_id: int | None = None,
    backend: str | None = None,
    strengths: Sequence[Any] | None = None,
    now: datetime | None = None,
) -> ScoreRecord:
    """Insert or update the one score row for `(listing, run, criteria_version)`.

    Never commits. Raises `ValueError` before any SQL when `criteria_version` is
    `None` or `confidence_tier` is not a member of `CONFIDENCE_TIERS`.
    """
    if criteria_version is None:
        raise ValueError(
            "criteria_version is mandatory and non-NULL: a NULL silently defeats "
            "uq_scores_listing_run_criteria because SQLite treats NULLs as distinct"
        )
    if confidence_tier not in CONFIDENCE_TIERS:
        raise ValueError(
            f"unknown confidence_tier {confidence_tier!r}; expected one of "
            f"{sorted(CONFIDENCE_TIERS)}"
        )

    moment = now if now is not None else datetime.now(UTC)
    values: dict[str, Any] = {
        "listing_id": int(listing_id),
        "run_id": int(run_id),
        "search_id": int(search_id) if search_id is not None else None,
        "criteria_version": int(criteria_version),
        "rubric_version": rubric_version,
        "backend": backend,
        "provider": provider,
        "model": model,
        "factor_scores_json": _factor_payload(sub_scores),
        "total_score": float(total_score) if total_score is not None else None,
        "weights_json": _weights_payload(weights),
        "confidence_tier": confidence_tier,
        "rationale": rationale,
        "strengths_json": [dict(entry) if isinstance(entry, Mapping) else entry for entry in (strengths or ())] or None,
        "gaps_json": [dict(entry) for entry in requirements],
        "created_at": moment,
    }
    # `created_at` is deliberately NOT in the update set: the row's creation moment
    # is the first time this triple was scored, not the latest correction to it.
    updatable = {
        key: value
        for key, value in values.items()
        if key not in {"listing_id", "run_id", "criteria_version", "created_at"}
    }
    statement = (
        sqlite_insert(Score)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["listing_id", "run_id", "criteria_version"],
            set_=updatable,
        )
    )
    async with session.begin_nested():
        await session.execute(statement)
        await session.flush()

    row = (
        await session.execute(
            select(Score).where(
                Score.listing_id == int(listing_id),
                Score.run_id == int(run_id),
                Score.criteria_version == int(criteria_version),
            )
        )
    ).scalar_one()
    return _to_record(row)


async def latest_for_listings(
    session: AsyncSession, listing_ids: Sequence[int]
) -> dict[int, ScoreRecord]:
    """The newest score per listing, keyed by listing id.

    One score row exists per RUN, so a naive join would yield duplicate rows for a
    listing scored by several runs (Pitfall 4). The newest is the row with the
    greatest `run_id`, then the greatest `id` as the deterministic tie-break.
    Never commits, never raises.
    """
    ids = [int(listing_id) for listing_id in (listing_ids or ())]
    if not ids:
        return {}

    rows = (
        (
            await session.execute(
                select(Score)
                .where(Score.listing_id.in_(ids))
                .order_by(Score.listing_id, Score.run_id.desc(), Score.id.desc())
            )
        )
        .scalars()
        .all()
    )

    newest: dict[int, ScoreRecord] = {}
    for row in rows:
        listing_id = int(row.listing_id)
        if listing_id not in newest:
            newest[listing_id] = _to_record(row)
    return newest


async def read_score_for_listing(
    session: AsyncSession, listing_id: int
) -> ScoreRecord | None:
    """The newest score row for one listing, or `None` when it has never been scored.

    The same newest-row rule as `latest_for_listings`. Never commits, never raises.
    """
    row = (
        await session.execute(
            select(Score)
            .where(Score.listing_id == int(listing_id))
            .order_by(Score.run_id.desc(), Score.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return _to_record(row) if row is not None else None


__all__ = [
    "CONFIDENCE_TIERS",
    "ScoreRecord",
    "latest_for_listings",
    "read_score_for_listing",
    "upsert_score",
]
