"""`run_pipeline()` — one callable, two triggers (Pattern 5 / D-22).

The manual trigger (`POST /runs`) enqueues it; Phase 8's scheduler will call the
same function. Manual and scheduled runs therefore stay behaviourally identical:
one log, one budget, one failure path.

The database is the single source of truth for run state — there is no in-memory
`RunState` registry (RESEARCH Open Question 3). The UI polls the `runs` row.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import Run, Source
from app.db.repositories.listing_repo import upsert_listing_source
from app.db.repositories.search_repo import (
    enabled_searches,
    rules_for_searches,
)
from app.domain.criteria import search_query_from
from app.ingest.sanitize import sanitize_listing
from app.pipeline.dedup_stage import DEDUP_STAGE, run_dedup_stage
from app.pipeline.filter_stage import FILTER_STAGE, run_filter_stage
from app.pipeline.stages import normalise_listing
from app.probe.survival import (
    compute_fill_rates,
    fill_rate_record_from_raw,
    record_baseline,
)
from app.sources import registry
from app.sources._ledger import record_fetch_outcome
from app.sources.base import (
    FetchBudget,
    FetchResult,
    JobSource,
    SearchQuery,
    compile_query_for_source,
)

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
            (await session.execute(select(Source).where(Source.enabled.is_(True)))).scalars().all()
        )

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


async def _fetch_one(
    adapter: JobSource, query: SearchQuery
) -> tuple[FetchResult, list[dict[str, Any]], list[dict[str, Any]]]:
    """A board's failure degrades the run; it never propagates (R1).

    The query is compiled against the board's declared capabilities BEFORE the
    fetch (R3/SRC-09): a filter the board cannot honour becomes a recorded
    warning rather than being dropped silently, and the adapter executes the
    compiled query. When nothing must be dropped the compiled query is the
    caller's query unchanged, so today's `default_query()` is unaffected.

    Returns the error-shaped warnings (for `runs.errors_json`, unchanged shape)
    **and** the structured `source`/`filter_name`/`reason` triples the stage log
    persists, so the run detail page can render a warning its own way.
    """
    compiled = compile_query_for_source(query, adapter.capabilities, source=adapter.name)
    warning_records: list[dict[str, Any]] = [
        {
            "source": warning.source,
            "filter_name": warning.filter_name,
            "reason": warning.reason,
        }
        for warning in compiled.warnings
    ]
    warnings: list[dict[str, Any]] = [
        {
            "source": adapter.name,
            "status": "warning",
            # The Phase-1 sentence is EXTENDED, not replaced: the same rules are
            # enforced locally as hard filters after the fetch (plan 02-05), so an
            # unsupported *fetch-side* filter is no longer "not applied at all".
            "error": (
                f"filter not applied: {warning.filter_name} — {warning.reason} "
                "(enforced locally as a hard filter after the fetch)"
            ),
        }
        for warning in compiled.warnings
    ]
    try:
        result = await adapter.fetch(compiled.query, build_budget())
    except Exception as exc:  # noqa: BLE001 — belt and braces around R1
        log.warning("pipeline.fetch_failed", source=adapter.name, error=str(exc))
        result = FetchResult(source=adapter.name, status="error", error=str(exc))
    return result, warnings, warning_records


async def _fetch_all(
    adapters: Sequence[JobSource], query: SearchQuery
) -> list[tuple[FetchResult, list[dict[str, Any]], list[dict[str, Any]]]]:
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
                log.warning("pipeline.persist_failed", source=result.source, error=str(exc))
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
                    error=result.error,
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
            log.warning("pipeline.ledger_failed", source=result.source, error=type(exc).__name__)

        await session.commit()

    return {
        "status": result.status,
        "fetched": len(result.items),
        "created": created,
        "updated": updated,
        "failed": failed,
        "requests_used": result.requests_used,
    }


#: Bounds on `runs.stage_log_json`. A pathological run must not be able to write an
#: unbounded blob, so the log keeps the last N stage entries and at most N errors
#: per entry. Deliberately small module constants, not Settings knobs: this is a
#: log-size guard, not a tunable operating limit.
STAGE_LOG_MAX_ENTRIES = 12
STAGE_LOG_MAX_ERRORS = 10


def _query_snapshot(query: SearchQuery) -> dict[str, Any]:
    """`SearchQuery` field values as JSON-plain values (never a dataclass)."""
    return {
        "keywords": query.keywords,
        "location": query.location,
        "distance_miles": query.distance_miles,
        "remote_only": query.remote_only,
        "salary_floor": query.salary_floor,
        "seniority": list(query.seniority),
        "hours_old": query.hours_old,
        "easy_apply": query.easy_apply,
        "offset": query.offset,
        "results_wanted": query.results_wanted,
    }


async def _build_criteria_snapshot(session: AsyncSession) -> dict[str, Any]:
    """The exact query + rule set this run will use, keyed by search id (D-33)."""
    searches = await enabled_searches(session)
    rules = await rules_for_searches(session, [record.id for record in searches])

    by_search: dict[int, list[Any]] = {}
    for rule in rules:
        by_search.setdefault(rule.search_id, []).append(rule)

    snapshot: dict[str, Any] = {}
    for record in searches:
        snapshot[str(record.id)] = {
            "name": record.name,
            "version": record.version,
            "query": _query_snapshot(search_query_from(record.criteria_json)),
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "kind": rule.kind,
                    "params": dict(rule.params_json or {}),
                    "position": rule.position,
                }
                for rule in by_search.get(record.id, [])
            ],
        }
    return snapshot


async def _write_criteria_snapshot(
    session_factory: async_sessionmaker[AsyncSession], run_id: int
) -> dict[str, Any]:
    """Write the snapshot BEFORE the fetch, and never rewrite it (CRIT-02).

    A run that fails mid-way still records what it attempted, and because the
    snapshot is taken before any edit can land, a later criteria edit cannot
    retroactively change what a completed run says it used.
    """
    async with session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None:  # pragma: no cover — the row was created by this call
            return {}
        snapshot = await _build_criteria_snapshot(session)
        run.criteria_snapshot_json = snapshot or None
        await session.commit()
    return snapshot


def _plain(value: Any) -> Any:
    """A JSON-plain value: ints/floats/strings/None pass through, bools stay bools."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _stage_entry(
    name: str,
    counts: Mapping[str, Any],
    errors: Sequence[str],
    **extra: Any,
) -> dict[str, Any]:
    """One bounded stage-log entry: plain values only, never a dataclass.

    `counts` mixes stage counters (ints) with the per-source persist summary (which
    carries a status string), so values are coerced to plain JSON types rather than
    assumed to be integers.
    """
    return {
        "stage": name,
        "counts": {str(key): _plain(value) for key, value in dict(counts).items()},
        "errors": [str(message) for message in list(errors)[:STAGE_LOG_MAX_ERRORS]],
        **extra,
    }


async def _finish(
    session_factory: async_sessionmaker[AsyncSession],
    run_id: int,
    *,
    status: str,
    source_counts: dict[str, Any],
    errors: list[dict[str, Any]],
    merged_count: int = 0,
    filtered_count: int = 0,
    stage_log: list[dict[str, Any]] | None = None,
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
        # RETIRED MEANING (D-30 / QUEUE-03): `deduped_count` used to be
        # `sum(created)` — the number of brand-new listings, which is not a dedup
        # signal at all. It is now the number of rows ABSORBED BY A MERGE this run,
        # so the merge rate is `deduped_count / fetched_count`. Do not restore the
        # old meaning.
        run.deduped_count = merged_count
        # The hard-filter stage (plan 02-05) is the writer `filtered_count` never
        # had: the number of listings the run's deterministic rules excluded.
        run.filtered_count = filtered_count
        # D-44's collapsible raw stage log, bounded so a pathological run cannot
        # write an unbounded blob.
        run.stage_log_json = stage_log or None
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
    merged_count = 0
    excluded_count = 0
    stage_log: list[dict[str, Any]] = []
    compile_warnings: list[dict[str, Any]] = []

    try:
        # Criteria snapshot (D-33 / CRIT-02): BEFORE the fetch, never rewritten, so
        # a run that fails mid-way still records what it attempted and a later
        # criteria edit cannot change what a completed run says it used.
        await _write_criteria_snapshot(session_factory, resolved_run_id)

        selected = await _resolve_adapters(session_factory, adapters)
        fetched = await _fetch_all(selected, query or default_query())
        if not selected:
            # Zero adapters resolved: the run fetched nothing, so `done` would be a
            # false success — the badge reads clean while the queue stays empty (and
            # the operator would read it as a scrape-survival result). The reason is
            # machine-readable in `errors_json`, in the same shape as a source error.
            errors.append({"source": "*", "status": "partial", "error": NO_SOURCES_REASON})
        results: list[FetchResult] = []
        for result, capability_warnings, warning_records in fetched:
            # A filter the board cannot honour is recorded, never silently dropped
            # (SRC-09/T-01-18). It is a warning, not a run failure: the fetch itself
            # may still be healthy. The same warnings also land in the stage log
            # below as structured triples (D-37 / T-02-19).
            errors.extend(capability_warnings)
            compile_warnings.extend(warning_records)
            results.append(result)
            source_counts[result.source] = await _persist_result(
                session_factory, result, resolved_run_id
            )
            stage_log.append(
                _stage_entry(f"persist:{result.source}", source_counts[result.source], [])
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
        persisted_failures = sum(int(counts.get("failed", 0)) for counts in source_counts.values())
        status = (
            "done"
            if results and all(r.status == "ok" for r in results) and persisted_failures == 0
            else "partial"
        )

        # Tier-2 dedup (D-30): post-persist, so both halves of a cross-source pair
        # exist before either is scored. The hard-filter stage runs after this one —
        # filtering first would discard the copy that carried the salary. Both are
        # best-effort on the run path: an internal failure is recorded and the run
        # still finishes, because the listings are already persisted.
        try:
            dedup_result = await run_dedup_stage(session_factory, resolved_run_id)
            merged_count = int(dedup_result.counts.get("merges", 0))
            stage_log.append(_stage_entry(DEDUP_STAGE, dedup_result.counts, dedup_result.errors))
            errors.extend(
                {"source": DEDUP_STAGE, "status": "warning", "error": message}
                for message in dedup_result.errors
            )
        except Exception as exc:  # noqa: BLE001 — dedup must not sink a saved run
            log.exception("pipeline.dedup_failed", run_id=resolved_run_id, error=str(exc))
            errors.append({"source": DEDUP_STAGE, "status": "failed", "error": str(exc)})

        # Hard-rule filter (FILT-01/02): deterministic, after dedup and before
        # `_finish`. This path makes NO model call — no LLM module is imported here
        # and no `llm_calls` row is ever written by it. Best-effort like dedup: a
        # filter failure is recorded and the run still finishes, because the
        # listings are already persisted.
        try:
            filter_result = await run_filter_stage(session_factory, resolved_run_id)
            excluded_count = int(filter_result.counts.get("excluded_listings", 0))
            stage_log.append(_stage_entry(FILTER_STAGE, filter_result.counts, filter_result.errors))
            errors.extend(
                {"source": FILTER_STAGE, "status": "warning", "error": message}
                for message in filter_result.errors
            )
        except Exception as exc:  # noqa: BLE001 — the filter must not sink a saved run
            log.exception("pipeline.filter_failed", run_id=resolved_run_id, error=str(exc))
            errors.append({"source": FILTER_STAGE, "status": "failed", "error": str(exc)})
    except Exception as exc:  # noqa: BLE001 — the background task must never die silently
        log.exception("pipeline.failed", error=str(exc))
        errors.append({"source": "*", "status": "failed", "error": str(exc)})
        status = "failed"

    # The criteria-compile entry is built here because the warnings are only known
    # after the fetch; it is prepended because it is chronologically first.
    stage_log.insert(
        0,
        _stage_entry(
            "criteria_compile",
            {"warnings": len(compile_warnings)},
            [],
            warnings=compile_warnings,
        ),
    )

    await _finish(
        session_factory,
        resolved_run_id,
        status=status,
        source_counts=source_counts,
        errors=errors,
        merged_count=merged_count,
        filtered_count=excluded_count,
        stage_log=stage_log[-STAGE_LOG_MAX_ENTRIES:],
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
