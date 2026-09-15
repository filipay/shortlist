"""`run_pipeline()` — one callable, two triggers (Pattern 5 / D-22).

The manual trigger (`POST /runs`) enqueues it; Phase 8's scheduler will call the
same function. Manual and scheduled runs therefore stay behaviourally identical:
one log, one budget, one failure path.

The database is the single source of truth for run state — there is no in-memory
`RunState` registry (RESEARCH Open Question 3). The UI polls the `runs` row.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import Run, Source
from app.db.repositories.listing_repo import upsert_listing_source
from app.ingest.sanitize import sanitize_listing
from app.pipeline.stages import normalise_listing
from app.probe.survival import (
    compute_fill_rates,
    fill_rate_record_from_raw,
    record_baseline,
)
from app.sources import registry
from app.sources._ledger import record_fetch_outcome
from app.sources.base import FetchBudget, FetchResult, JobSource, SearchQuery

log = structlog.get_logger(__name__)

MANUAL = "manual"
TERMINAL_STATUSES = frozenset({"done", "partial", "failed"})

#: Recorded in `runs.errors_json` under source `*` when a run resolves zero
#: adapters. It stays `partial`, never `done`: nothing ran, so a clean badge would
#: be a false success. The `runs.status` CHECK permits only
#: running/done/failed/partial, so no new status value is introduced.
NO_SOURCES_REASON = "no enabled sources resolved from the adapter registry"


def default_query() -> SearchQuery:
    """The Phase-1 search intent, with every limit read from settings (PLAT-04).

    This is deliberately a function rather than a module constant: a constant
    would freeze the ban-risk envelope at import time and silently ignore an
    operator override, which is the exact "threshold as a constant" failure
    `probe_*` exists to prevent. Only the keywords are literals — they are a
    product string, not a limit.
    """
    return SearchQuery(
        keywords="software engineer",
        location=settings.probe_query_location,
        results_wanted=settings.probe_results_wanted,
    )


def build_budget(*, now: datetime | None = None) -> FetchBudget:
    """One `FetchBudget` per source, with every ceiling read from settings."""
    moment = now or datetime.now(UTC)
    return FetchBudget(
        max_requests=settings.probe_max_requests,
        max_results=settings.probe_max_results,
        max_detail_fetches=settings.probe_max_detail_fetches,
        deadline=moment + timedelta(seconds=settings.probe_deadline_seconds),
    )


async def _resolve_adapters(
    session_factory: async_sessionmaker[AsyncSession],
    adapters: Sequence[JobSource] | None,
) -> list[JobSource]:
    """Explicitly injected adapters win; otherwise the enabled `sources` rows."""
    if adapters is not None:
        return list(adapters)

    async with session_factory() as session:
        rows = (
            await session.execute(select(Source).where(Source.enabled.is_(True)))
        ).scalars().all()

    resolved: list[JobSource] = []
    for row in rows:
        try:
            adapter_cls = registry.get(row.name)
        except registry.UnknownAdapterError:
            # An enabled `sources` row with no implementation degrades that board
            # only — it must never abort the run.
            log.warning("pipeline.unknown_source", source=row.name)
            continue
        resolved.append(adapter_cls())
    return resolved


async def _fetch_one(adapter: JobSource, query: SearchQuery) -> FetchResult:
    """A board's failure degrades the run; it never propagates (R1)."""
    try:
        return await adapter.fetch(query, build_budget())
    except Exception as exc:  # noqa: BLE001 — belt and braces around R1
        log.warning("pipeline.fetch_failed", source=adapter.name, error=str(exc))
        return FetchResult(source=adapter.name, status="error", error=str(exc))


async def _fetch_all(
    adapters: Sequence[JobSource], query: SearchQuery
) -> list[FetchResult]:
    """Fan out concurrently — one call per board, one budget each."""
    if not adapters:
        return []
    return list(await asyncio.gather(*(_fetch_one(adapter, query) for adapter in adapters)))


async def _persist_result(
    session_factory: async_sessionmaker[AsyncSession],
    result: FetchResult,
    run_id: int,
) -> dict[str, Any]:
    """sanitise -> normalise -> two-key upsert, one transaction per board.

    Each item is wrapped in a SAVEPOINT: a row that fails to persist (a bad
    field, a missing `sources` row for an injected adapter) rolls back by itself
    and can never leave a half-written `listings` row behind.
    """
    now = datetime.now(UTC)
    created = 0
    updated = 0
    failed = 0

    async with session_factory() as session:
        for raw in result.items:
            try:
                async with session.begin_nested():
                    sanitised, _report = await sanitize_listing(raw)
                    normalised = normalise_listing(sanitised)
                    outcome = await upsert_listing_source(
                        session,
                        source=result.source,
                        norm=normalised,
                        run_id=run_id,
                        now=now,
                    )
            except Exception as exc:  # noqa: BLE001 — one bad row must not kill the run
                failed += 1
                log.warning(
                    "pipeline.persist_failed", source=result.source, error=str(exc)
                )
                continue
            if outcome.kind == "created":
                created += 1
            else:
                updated += 1

        # The politeness ledger and the S2 baseline anchor. Both go through a
        # SAVEPOINT: a bookkeeping failure must not abort a run whose listings
        # already persisted (R1), and it must not poison the outer transaction.
        try:
            async with session.begin_nested():
                # One row per outbound request (D-03's ledger). Written even when
                # the board returned no rows, because a parse-side miss is exactly
                # what must be visible later.
                await record_fetch_outcome(
                    session,
                    source=result.source,
                    run_id=run_id,
                    result_status=result.status,
                    parsed_items=len(result.items),
                    now=now,
                )
                if result.status == "ok" and result.items:
                    # Recorded once, on the first successful run per source; never
                    # overwritten, so the anchor S2 compares against survives.
                    await record_baseline(
                        session,
                        source=result.source,
                        fill_rates=compute_fill_rates(
                            [fill_rate_record_from_raw(item) for item in result.items]
                        ),
                        now=now,
                    )
        except Exception as exc:  # noqa: BLE001 — bookkeeping is not the payload
            log.warning(
                "pipeline.ledger_failed", source=result.source, error=type(exc).__name__
            )

        await session.commit()

    return {
        "status": result.status,
        "fetched": len(result.items),
        "created": created,
        "updated": updated,
        "failed": failed,
        "requests_used": result.requests_used,
    }


async def _finish(
    session_factory: async_sessionmaker[AsyncSession],
    run_id: int,
    *,
    status: str,
    source_counts: dict[str, Any],
    errors: list[dict[str, Any]],
) -> None:
    async with session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None:  # pragma: no cover — the row was created by this call
            return
        run.status = status
        run.finished_at = datetime.now(UTC)
        run.source_counts_json = source_counts
        run.errors_json = errors or None
        run.fetched_count = sum(int(c.get("fetched", 0)) for c in source_counts.values())
        run.deduped_count = sum(int(c.get("created", 0)) for c in source_counts.values())
        await session.commit()


async def run_pipeline(
    trigger: str,
    search_id: int | None,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    adapters: Sequence[JobSource] | None = None,
    query: SearchQuery | None = None,
    run_id: int | None = None,
) -> int:
    """Run one pipeline pass and return its `runs.id`.

    `run_id` lets a caller that already created (and committed) the `runs` row —
    so it could answer a request with a run id immediately — hand that row to the
    pipeline instead of the pipeline creating a second one. Phase 8's scheduler
    simply omits it and the pipeline creates its own row.

    `adapters` is an explicit injection seam for tests and for callers that
    already resolved the enabled sources. Never awaited inside a request handler.
    """
    if run_id is None:
        async with session_factory() as session:
            run = Run(
                search_id=search_id,
                trigger=trigger,
                status="running",
                started_at=datetime.now(UTC),
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            resolved_run_id = int(run.id)
    else:
        resolved_run_id = run_id

    source_counts: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []

    try:
        selected = await _resolve_adapters(session_factory, adapters)
        results = await _fetch_all(selected, query or default_query())
        if not selected:
            # Zero adapters resolved: the run fetched nothing, so `done` would be a
            # false success — the badge reads clean while the queue stays empty (and
            # the operator would read it as a scrape-survival result). The reason is
            # machine-readable in `errors_json`, in the same shape as a source error.
            errors.append(
                {"source": "*", "status": "partial", "error": NO_SOURCES_REASON}
            )
        for result in results:
            source_counts[result.source] = await _persist_result(
                session_factory, result, resolved_run_id
            )
            if result.status != "ok":
                errors.append(
                    {
                        "source": result.source,
                        "status": result.status,
                        "error": result.error,
                    }
                )
        # A run is only `done` when it actually ran, every board was fully
        # healthy, AND every fetched item persisted. A `partial` that renders
        # like a clean success is a trust failure (Pitfall 10) — and so is
        # `done` for a run that resolved no sources, or whose every item was
        # rejected on write (e.g. an FK to `sources.name`).
        persisted_failures = sum(
            int(counts.get("failed", 0)) for counts in source_counts.values()
        )
        status = (
            "done"
            if results
            and all(r.status == "ok" for r in results)
            and persisted_failures == 0
            else "partial"
        )
    except Exception as exc:  # noqa: BLE001 — the background task must never die silently
        log.exception("pipeline.failed", error=str(exc))
        errors.append({"source": "*", "status": "failed", "error": str(exc)})
        status = "failed"

    await _finish(
        session_factory,
        resolved_run_id,
        status=status,
        source_counts=source_counts,
        errors=errors,
    )
    log.info(
        "pipeline.finished",
        run_id=resolved_run_id,
        trigger=trigger,
        status=status,
        sources=sorted(source_counts),
    )
    return resolved_run_id


__all__ = [
    "MANUAL",
    "NO_SOURCES_REASON",
    "TERMINAL_STATUSES",
    "build_budget",
    "default_query",
    "run_pipeline",
]
