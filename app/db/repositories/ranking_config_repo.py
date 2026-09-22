"""The global ranking-weights document — the only place its SQL lives (D-99).

House rules, as everywhere in `app/db/repositories/`:

* repositories are the **only** place SQL lives;
* they take an `AsyncSession` explicitly and **never commit** — the caller owns
  the single commit;
* writes are wrapped in a SAVEPOINT (`session.begin_nested()`) so a failure here
  cannot poison the caller's outer transaction;
* `now` is injectable so a caller (or a test) can pin the clock.

One row, `id = 1`, enforced by `ck_ranking_config_singleton`. The read is **total**:
an absent row falls back to `rubric.DEFAULT_WEIGHTS`, an unknown key is dropped and
a missing key is filled from the defaults, so a half-written document can never
crash a page render. The write is **strict**: every key must be a member of
`rubric.FACTORS` and every value a finite float `>= 0.0`, and a clear `ValueError`
is raised before any SQL otherwise — validation at the storage boundary (D-34).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RankingConfig
from app.domain import rubric

#: The pinned singleton row id (mirrors `ck_ranking_config_singleton`).
SINGLETON_ID = 1


def _as_float(value: Any) -> float | None:
    """A finite float, or `None` when the stored value is unusable."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


async def read_weights(session: AsyncSession) -> dict[str, float]:
    """The stored weights document, or the rubric defaults when no row exists.

    Tolerant by construction: unknown keys are dropped and missing keys are filled
    from `rubric.DEFAULT_WEIGHTS`, so a partially-written document still yields a
    complete, usable weight set. Never commits.
    """
    row = await session.get(RankingConfig, SINGLETON_ID)
    stored = row.weights_json if row is not None else None
    document = stored if isinstance(stored, Mapping) else {}

    weights: dict[str, float] = {}
    for factor in rubric.FACTORS:
        value = _as_float(document.get(factor))
        fallback = float(rubric.DEFAULT_WEIGHTS[factor])
        weights[factor] = fallback if value is None else value
    return weights


async def write_weights(
    session: AsyncSession,
    weights: Mapping[str, float],
    *,
    now: datetime | None = None,
) -> None:
    """Validate and upsert the one weights row. Never commits.

    Raises `ValueError` **before any SQL** when a key is not a factor or a value is
    not a finite float `>= 0.0` — the caller gets a legible storage-boundary error
    rather than a raw `IntegrityError` or a silently dropped key.
    """
    unknown = sorted(str(key) for key in weights if key not in rubric.FACTORS)
    if unknown:
        raise ValueError(
            f"unknown weight factor(s) {unknown}; expected members of {list(rubric.FACTORS)}"
        )
    missing = [factor for factor in rubric.FACTORS if factor not in weights]
    if missing:
        raise ValueError(f"missing weight factor(s) {missing}")

    document: dict[str, float] = {}
    for factor in rubric.FACTORS:
        value = _as_float(weights[factor])
        if value is None or value < 0.0:
            raise ValueError(
                f"weight for {factor!r} must be a finite float >= 0.0, "
                f"got {weights[factor]!r}"
            )
        document[factor] = value

    moment = now if now is not None else datetime.now(UTC)
    statement = (
        sqlite_insert(RankingConfig)
        .values(id=SINGLETON_ID, weights_json=document, updated_at=moment)
        .on_conflict_do_update(
            index_elements=["id"],
            set_={"weights_json": document, "updated_at": moment},
        )
    )
    async with session.begin_nested():
        await session.execute(statement)
        await session.flush()


__all__ = ["SINGLETON_ID", "read_weights", "write_weights"]
