"""Source repository — the probe write path (SRC-07 / D-03(c)).

The pipeline owns the ingest side of the `sources` table. What Phase 1 needs from
it beyond that is small and split by concern: which sources are enabled (the
probe's resolution step), the write path for a probe result (`last_probe_at` and
`health`), and — in plan 01-06's third task — the per-source health read model the
UI strip renders.

Nothing here imports `app.probe`: the status vocabulary is validated locally and
enforced by the `ck_sources_health` CHECK constraint.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Source

#: Mirrors `ck_sources_health` on the `sources` table.
VALID_HEALTH: frozenset[str] = frozenset({"ok", "degraded", "unreachable"})


async def enabled_source_names(session: AsyncSession) -> list[str]:
    """Names of the enabled `sources` rows, deterministically ordered."""
    rows = (
        await session.execute(
            select(Source.name).where(Source.enabled.is_(True)).order_by(Source.name)
        )
    ).scalars().all()
    return list(rows)


async def record_probe_result(
    session: AsyncSession,
    *,
    source: str,
    status: str,
    now: datetime | None = None,
) -> bool:
    """Stamp `last_probe_at` and `health` on one source row.

    Returns `False` when no row carries that name — a registered adapter with no
    `sources` row is not an error, and the probe must not fail over it.
    """
    if status not in VALID_HEALTH:
        raise ValueError(f"invalid probe status {status!r}; expected one of {sorted(VALID_HEALTH)}")

    row = await session.scalar(select(Source).where(Source.name == source))
    if row is None:
        return False

    row.last_probe_at = now or datetime.now(UTC)
    row.health = status
    await session.flush()
    return True


__all__ = ["VALID_HEALTH", "enabled_source_names", "record_probe_result"]
