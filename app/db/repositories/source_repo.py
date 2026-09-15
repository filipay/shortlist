"""Source repository — the probe write path and the per-source health read model.

The pipeline owns the ingest side of the `sources` table. What Phase 1 needs from
it beyond that is small and split by concern: which sources are enabled and the
write path for a probe result (`last_probe_at`, `health`), then the read model
SRC-07 / D-13 requires the UI strip to render — last success, listings returned
and per-field fill-rate.

Nothing here imports `app.probe`: the status vocabulary is validated locally and
enforced by the `ck_sources_health` CHECK constraint.

**Fill-rate is computed over normalised records** (RESEARCH §S2), so an
all-blank description counts as empty rather than as a non-null string. The schema
has no direct listing-to-run link, so a run's records are the source's rows whose
`last_seen_at` falls at or after that run's `started_at` — the pipeline stamps
every row it touches with the run's own clock.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Listing, ListingSource, Run, Source

#: Mirrors `ck_sources_health` on the `sources` table.
VALID_HEALTH: frozenset[str] = frozenset({"ok", "degraded", "unreachable"})

#: How far back the read model looks for per-source history.
RECENT_RUN_LIMIT = 20

#: `(label, listings attribute, listing_sources attribute)` for the S2 fill-rate.
#: `salary_min`/`salary_max` are reported but never *targeted*: JobSpy's
#: description-salary extraction is USA-only, so an Irish search is structurally
#: low here (RESEARCH §S2) and only deltas are meaningful.
FILL_RATE_FIELDS: tuple[tuple[str, str, str | None], ...] = (
    ("title", "title", None),
    ("company_name", "company_norm", None),
    ("location_raw", "location_raw", None),
    ("description", "description", None),
    ("posted_at", "posted_at", None),
    ("salary_min", "salary_min", None),
    ("salary_max", "salary_max", None),
    ("source_listing_id", "source_listing_id", "source_listing_id"),
    ("direct_url", "direct_url", "direct_url"),
)


@dataclass(frozen=True)
class SourceHealth:
    """One row of the per-source health strip (SRC-07 / D-13)."""

    name: str
    enabled: bool
    health: str | None
    last_probe_at: datetime | None
    last_success_at: datetime | None
    listings_returned: int
    field_fill_rate: dict[str, float] = field(default_factory=dict)


def _populated(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _fill_rate(rows: Sequence[tuple[Listing, ListingSource]]) -> dict[str, float]:
    """Populated-over-total per field, over normalised records."""
    total = len(rows)
    if total == 0:
        return {}

    rates: dict[str, float] = {}
    for label, listing_attr, source_attr in FILL_RATE_FIELDS:
        populated = 0
        for listing, listing_source in rows:
            value = (
                getattr(listing_source, source_attr)
                if source_attr is not None
                else getattr(listing, listing_attr)
            )
            if _populated(value):
                populated += 1
        rates[label] = populated / total
    return rates


def _source_entry(run: Run, name: str) -> dict[str, Any] | None:
    counts = run.source_counts_json
    if not isinstance(counts, dict):
        return None
    entry = counts.get(name)
    return entry if isinstance(entry, dict) else None


def _latest_run_for(runs: Sequence[Run], name: str) -> Run | None:
    for run in runs:
        if _source_entry(run, name) is not None:
            return run
    return None


def _last_success_run(runs: Sequence[Run], name: str) -> Run | None:
    """The most recent run in which *this source* reported `ok`."""
    for run in runs:
        entry = _source_entry(run, name)
        if entry is not None and entry.get("status") == "ok":
            return run
    return None


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
        raise ValueError(
            f"invalid probe status {status!r}; expected one of {sorted(VALID_HEALTH)}"
        )

    row = await session.scalar(select(Source).where(Source.name == source))
    if row is None:
        return False

    row.last_probe_at = now or datetime.now(UTC)
    row.health = status
    await session.flush()
    return True


async def get_source_health(session: AsyncSession) -> list[SourceHealth]:
    """The per-source read model: liveness, last success, volume and fill-rate."""
    sources = (
        await session.execute(select(Source).order_by(Source.name))
    ).scalars().all()
    runs = (
        await session.execute(
            select(Run)
            .order_by(Run.started_at.desc(), Run.id.desc())
            .limit(RECENT_RUN_LIMIT)
        )
    ).scalars().all()

    health: list[SourceHealth] = []
    for source in sources:
        latest = _latest_run_for(runs, source.name)
        last_success = _last_success_run(runs, source.name)

        rows: list[tuple[Listing, ListingSource]] = []
        if latest is not None and latest.started_at is not None:
            rows = list(
                (
                    await session.execute(
                        select(Listing, ListingSource)
                        .join(ListingSource, ListingSource.listing_id == Listing.id)
                        .where(
                            ListingSource.source == source.name,
                            ListingSource.last_seen_at >= latest.started_at,
                        )
                    )
                ).all()
            )

        returned = 0
        if latest is not None:
            entry = _source_entry(latest, source.name) or {}
            try:
                returned = int(entry.get("fetched") or 0)
            except (TypeError, ValueError):
                returned = 0
        if not returned and rows:
            returned = len(rows)

        health.append(
            SourceHealth(
                name=source.name,
                enabled=bool(source.enabled),
                health=source.health,
                last_probe_at=source.last_probe_at,
                last_success_at=last_success.started_at if last_success else None,
                listings_returned=returned,
                field_fill_rate=_fill_rate(rows),
            )
        )

    return health


__all__ = [
    "FILL_RATE_FIELDS",
    "RECENT_RUN_LIMIT",
    "VALID_HEALTH",
    "SourceHealth",
    "enabled_source_names",
    "get_source_health",
    "record_probe_result",
]
