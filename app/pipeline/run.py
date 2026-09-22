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
from app.db.models import QueueState, Run, Search, Source
from app.db.repositories.exclusion_repo import (
    excluded_counts_for_run,
    rule_counts_for_listings,
)
from app.db.repositories.listing_repo import upsert_listing_source
from app.db.repositories.search_repo import (
    active_listings,
    enabled_searches,
    rules_for_searches,
    search_by_id,
)
from app.domain.criteria import search_query_from
from app.domain.run_reason import RunCounts, compute_empty_reason
from app.ingest.sanitize import sanitize_listing
from app.llm import get_llm_backend
from app.llm.base import LLMBackend
from app.pipeline.dedup_stage import DEDUP_STAGE, run_dedup_stage
from app.pipeline.filter_stage import FILTER_STAGE, run_filter_stage
from app.pipeline.rank import RANK_STAGE, start_ranking_task
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


async def resolve_enabled_adapters(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[JobSource]:
    """The enabled adapters, resolved through the `sources` rows and the registry.

    A thin public seam over `_resolve_adapters`, for a caller that wants the
    capabilities *without* running a pipeline (the criteria page's pre-run report,
    D-37). It reuses the run path's one resolution rather than a second SQL copy.
    """
    return await _resolve_adapters(session_factory, None)


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


#: Fetch statuses ordered from best to worst. A source fetched once per search can
#: report a different status each time; the merged status must be the worst one.
_FETCH_STATUS_SEVERITY: tuple[str, ...] = (
    "ok",
    "partial",
    "rate_limited",
    "blocked",
    "error",
)
_FETCH_STATUS_RANK: dict[str, int] = {
    status: rank for rank, status in enumerate(_FETCH_STATUS_SEVERITY)
}


def _worst_fetch_status(statuses: Sequence[str]) -> str:
    """The worst of several statuses for one source (lowest quality wins).

    The global run fetches a source once per enabled search, so it can come back
    `ok` for one search and `error` for another. This reduces them using the
    documented severity order `error` > `blocked` > `rate_limited` > `partial` >
    `ok`: `ok` only when EVERY fetch was `ok`, otherwise the strongest failure
    signal, so a second healthy search can never launder a broken board into a
    clean badge. An unrecognised status ranks worst (`error`) rather than being
    silently treated as healthy.
    """
    worst = "ok"
    worst_rank = 0
    for status in statuses:
        text = str(status)
        rank = _FETCH_STATUS_RANK.get(text, len(_FETCH_STATUS_SEVERITY))
        if rank >= worst_rank:
            worst = text
            worst_rank = rank
    return worst


def _merge_source_counts(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> dict[str, Any]:
    """Merge two per-fetch count dicts for the SAME source into one entry.

    The union run fetches a source once per enabled search, but
    `runs.source_counts_json` and the `persist:<source>` stage entry are a
    one-entry-per-source contract, so the numeric counters are summed and the
    status is reduced with `_worst_fetch_status`.
    """
    return {
        "status": _worst_fetch_status(
            (str(left.get("status", "")), str(right.get("status", "")))
        ),
        "fetched": int(left.get("fetched", 0)) + int(right.get("fetched", 0)),
        "created": int(left.get("created", 0)) + int(right.get("created", 0)),
        "updated": int(left.get("updated", 0)) + int(right.get("updated", 0)),
        "failed": int(left.get("failed", 0)) + int(right.get("failed", 0)),
        "requests_used": int(left.get("requests_used", 0))
        + int(right.get("requests_used", 0)),
    }


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
                    sanitised, report = await sanitize_listing(raw)
                    # §6.3: instruction-like text is a FINDING TO RECORD — never
                    # obeyed, never silently stripped. The payload is counts only (a
                    # bool plus an int); the sanitize module never exposes the
                    # matched text, so there is nothing here that could carry prose.
                    # A clean listing passes `None` so the column stays NULL and a
                    # previously recorded signal is never clobbered (T-3-21).
                    signals = {
                        "instruction_like": report.instruction_like,
                        "patterns_matched": report.patterns_matched,
                    }
                    normalised = normalise_listing(
                        sanitised,
                        quality_signals=(
                            signals
                            if (report.instruction_like or report.patterns_matched)
                            else None
                        ),
                    )
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


async def _build_criteria_snapshot(
    session: AsyncSession, *, search_id: int | None = None
) -> dict[str, Any]:
    """The exact query + rule set this run will use, keyed by search id (D-33).

    With `search_id` set (D-45's per-search run) the snapshot has exactly one entry
    and is that search's query+rules — so a "Run this one" is reproducible on its
    own, not blurred into the union. With `search_id` `None` it is the union of the
    enabled searches, unchanged from plan 02-05.
    """
    if search_id is not None:
        record = await search_by_id(session, search_id)
        searches = [record] if record is not None else []
    else:
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
    session_factory: async_sessionmaker[AsyncSession],
    run_id: int,
    *,
    search_id: int | None = None,
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
        snapshot = await _build_criteria_snapshot(session, search_id=search_id)
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


async def _read_watermark(session: AsyncSession) -> datetime | None:
    """The queue's last-visit watermark, or `None` when the queue was never opened.

    Read only. Advancing it is plan 02-07's queue-open behaviour: a run must never
    move the boundary it is being measured against, or `nothing_new` would become
    unfalsifiable.
    """
    row = (
        (await session.execute(select(QueueState).order_by(QueueState.id).limit(1)))
        .scalars()
        .first()
    )
    return row.last_queue_view_at if row is not None else None


def _is_new(first_seen_at: datetime | None, watermark: datetime | None) -> bool:
    """True when a listing is new relative to the watermark.

    `watermark is None` means "never viewed", so every listing counts as new —
    otherwise an untouched queue would report `nothing_new` on its first run and
    hide the very listings it is meant to show. The two values come from the same
    SQLite file, but their `tzinfo` is normalised anyway so the comparison can
    never raise on a mixed-naive datetime pair.
    """
    if watermark is None:
        return True
    if first_seen_at is None:
        return False
    left = first_seen_at.replace(tzinfo=None) if first_seen_at.tzinfo else first_seen_at
    right = watermark.replace(tzinfo=None) if watermark.tzinfo else watermark
    return left > right


async def _assemble_run_reason(
    session_factory: async_sessionmaker[AsyncSession],
    run_id: int,
    *,
    adapters_resolved: int,
    source_counts: Mapping[str, Any],
    capability_warnings: Sequence[Mapping[str, Any]],
) -> tuple[str, dict[str, Any]]:
    """Assemble `RunCounts`, decide the reason, and build the counts payload.

    Every read here is bookkeeping, not the payload: an unreadable watermark or
    survivor set degrades to zeroes and the run still finishes with a reason,
    because its listings are already persisted (R1). The reason itself is decided
    by the pure `compute_empty_reason` — no I/O, no model call, no `Settings`.
    """
    excluded_by_rule: dict[str, int] = {}
    survivors = 0
    new_since_watermark = 0
    watermark: datetime | None = None

    try:
        async with session_factory() as session:
            watermark = await _read_watermark(session)
            excluded_by_rule = await excluded_counts_for_run(session, run_id=run_id)
            listings = await active_listings(session, run_id=run_id)
            excluded_ids = await rule_counts_for_listings(session, run_id=run_id)

        # A survivor is a listing this run touched that no firing rule removed.
        # `active_listings` already skips absorbed twins, so this matches what the
        # queue will actually show (plan 02-07's visibility predicate is additive).
        surviving = [record for record in listings if record.id not in excluded_ids]
        survivors = len(surviving)
        new_since_watermark = sum(
            1 for record in surviving if _is_new(record.first_seen_at, watermark)
        )
    except Exception as exc:  # noqa: BLE001 — bookkeeping is not the payload
        log.warning("pipeline.reason_counts_failed", run_id=run_id, error=type(exc).__name__)

    counts = RunCounts(
        adapters_resolved=int(adapters_resolved),
        statuses=tuple(str(values.get("status", "")) for values in source_counts.values()),
        fetched=sum(int(values.get("fetched", 0)) for values in source_counts.values()),
        excluded_by_rule=dict(excluded_by_rule),
        survivors=int(survivors),
        new_since_watermark=int(new_since_watermark),
    )
    reason = compute_empty_reason(counts)

    # The decomposition behind the reason. `sources` and `excluded_by_rule` are
    # plain-value copies so the payload is JSON-serialisable by construction.
    payload: dict[str, Any] = {
        "adapters_resolved": counts.adapters_resolved,
        "sources": {name: _plain_values(values) for name, values in source_counts.items()},
        "excluded_by_rule": {
            str(rule_id): int(value) for rule_id, value in counts.excluded_by_rule.items()
        },
        "survivors": counts.survivors,
        # Tier-1 key hits: rows this run saw before and updated, not new listings.
        "duplicates_already_seen": sum(
            int(values.get("updated", 0)) for values in source_counts.values()
        ),
        "new_since_watermark": counts.new_since_watermark,
        "watermark": watermark.isoformat() if watermark is not None else None,
        "capability_warnings": [
            dict(warning) for warning in list(capability_warnings)[:STAGE_LOG_MAX_ERRORS]
        ],
    }
    return reason, payload


def _plain_values(values: Mapping[str, Any]) -> dict[str, Any]:
    """A JSON-plain copy of a per-source counts mapping."""
    return {str(key): _plain(value) for key, value in dict(values).items()}


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
    reason: str | None = None,
    reason_counts: dict[str, Any] | None = None,
    llm_calls: int | None = None,
    llm_tokens: int | None = None,
) -> None:
    async with session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None:  # pragma: no cover — the row was created by this call
            return
        run.status = status
        run.finished_at = datetime.now(UTC)
        run.source_counts_json = source_counts
        run.errors_json = errors or None
        # The sum of listings returned across EVERY fetch. A union run fetches one
        # source once per enabled search, so the same listing can be counted more
        # than once when two searches return it: that is intentional (the fetch
        # happened), and Tier-1 upsert plus `duplicates_already_seen` already
        # account for the repeated row — `created` counts it once, every later
        # encounter is an `updated`.
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
        # RUN-03 / D-44 — the reason is written on EVERY run, not only when the
        # queue is empty: it summarises the run's outcome and plan 02-10's history
        # page renders it unconditionally. The counts are the decomposition the
        # sentence is rendered FROM, never a stored sentence.
        run.reason = reason
        run.reason_counts_json = reason_counts or None
        # D-49 / Phase-5 SEAM. This is the writer Phase 5's ranking caller will use,
        # fed by `llm_call_repo.llm_totals_for_run`. Phase 3 deliberately wires NO
        # caller: one would violate D-49 and break the `LlmCall == 0` guard in
        # `tests/pipeline/test_filter_stage.py`. Assigned only when supplied, so a
        # later non-LLM run never zeros a count an LLM run recorded.
        if llm_calls is not None:
            run.llm_calls = llm_calls
        if llm_tokens is not None:
            run.llm_tokens = llm_tokens
        # `ranked_count` is deliberately NOT touched — Phase 5 owns it.
        await session.commit()


async def _stamp_last_run(
    session_factory: async_sessionmaker[AsyncSession],
    search_ids: Sequence[int],
    *,
    now: datetime | None = None,
) -> None:
    """Record the per-search `last_run_at` for the searches this run fetched for.

    The union run now fetches every enabled search's criteria, so each of those
    searches is fresh and must say so on `/searches`; PITFALLS m10 is about never
    inventing a *global* freshness, not about withholding a per-search one. A search
    the run did not fetch is never touched — the explicit-`query` path and the
    zero-enabled `default_query()` fallback are not attributable to a saved search.
    One timestamp is applied to every row, so a multi-search run's freshness is a
    single fact rather than N near-identical ones.
    """
    if not search_ids:
        return
    moment = now or datetime.now(UTC)
    async with session_factory() as session:
        for search_id in search_ids:
            row = await session.get(Search, search_id)
            if row is None:
                continue
            row.last_run_at = moment
        await session.commit()


async def _resolve_fetch_queries(
    session_factory: async_sessionmaker[AsyncSession],
    query: SearchQuery | None,
    search_id: int | None,
) -> list[tuple[int | None, SearchQuery]]:
    """The ``(search_id, query)`` fetch plan for this run, in a deterministic order.

    * An explicit ``query`` wins outright: a single entry, so every injected-query
      caller (tests, the scheduler) fetches exactly once.
    * ``search_id`` set (D-45's "Run this one") scopes to *that* search's criteria.
      A missing search keeps today's fallback: ``[(None, default_query())]``.
    * Neither (the global ``POST /runs``) fetches the **union of every enabled
      search**: one entry per search, ordered by ``searches.id`` (the repository's
      ``enabled_searches`` order). This is the defect fix — the global run used to
      silently fall back to the hardcoded Phase-1 ``default_query()`` and never
      used a saved search's criteria. With **no** enabled searches it still falls
      back to ``[(None, default_query())]`` so ``POST /runs`` and
      ``scripts/compose-smoke.sh`` keep working with zero configuration.
    """
    if query is not None:
        return [(search_id, query)]
    if search_id is not None:
        async with session_factory() as session:
            record = await search_by_id(session, search_id)
        if record is not None:
            return [(search_id, search_query_from(record.criteria_json))]
        return [(None, default_query())]

    async with session_factory() as session:
        records = await enabled_searches(session)
    if not records:
        return [(None, default_query())]
    return [(int(record.id), search_query_from(record.criteria_json)) for record in records]


async def run_pipeline(
    trigger: str,
    search_id: int | None,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    adapters: Sequence[JobSource] | None = None,
    query: SearchQuery | None = None,
    run_id: int | None = None,
    llm: LLMBackend | None = None,
) -> int:
    """Run one pipeline pass and return its `runs.id`.

    `run_id` lets a caller that already created (and committed) the `runs` row —
    so it could answer a request with a run id immediately — hand that row to the
    pipeline instead of the pipeline creating a second one. Phase 8's scheduler
    simply omits it and the pipeline creates its own row.

    `adapters` is an explicit injection seam for tests and for callers that
    already resolved the enabled sources. Never awaited inside a request handler.

    `llm` is the backend the detached ranking task will use, defaulting to
    `get_llm_backend()`. It is threaded explicitly so a caller's override (the
    default test lane's offline stub) actually reaches the task (Pitfall 7).
    """
    backend = llm if llm is not None else get_llm_backend()
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
    adapters_resolved = 0
    stage_log: list[dict[str, Any]] = []
    compile_warnings: list[dict[str, Any]] = []
    # The searches this run's fetch plan actually used, for the post-run
    # `last_run_at` stamp. Pre-declared so a failure before the plan resolves leaves
    # it empty rather than raising in the `finally`-style tail below.
    stamped_search_ids: list[int] = []

    try:
        # Criteria snapshot (D-33 / CRIT-02): BEFORE the fetch, never rewritten, so
        # a run that fails mid-way still records what it attempted and a later
        # criteria edit cannot change what a completed run says it used.
        await _write_criteria_snapshot(session_factory, resolved_run_id, search_id=search_id)

        selected = await _resolve_adapters(session_factory, adapters)
        adapters_resolved = len(selected)
        # The global run fetches the union of every enabled search, so the fetch
        # plan is a list of (search_id, query) rather than one query. An explicit
        # query and a per-search run still resolve to exactly one entry.
        fetch_plan = await _resolve_fetch_queries(session_factory, query, search_id)
        # The saved searches this run used: an explicit `query` is not attributable to
        # a search, and a zero-enabled run falls back to `default_query()` with a
        # `None` id, so neither contributes a search to stamp.
        if query is None:
            stamped_search_ids = [
                scoped_id for scoped_id, _ in fetch_plan if scoped_id is not None
            ]
        if not selected:
            # Zero adapters resolved: the run fetched nothing, so `done` would be a
            # false success — the badge reads clean while the queue stays empty (and
            # the operator would read it as a scrape-survival result). The reason is
            # machine-readable in `errors_json`, in the same shape as a source error.
            errors.append({"source": "*", "status": "partial", "error": NO_SOURCES_REASON})

        results: list[FetchResult] = []
        # `(adapter.name, query)` already fetched this run. Two searches whose
        # criteria compile to an equal frozen `SearchQuery` produce the same rows
        # (there is no listing->search link), so the second fetch is pure
        # duplication: skipping it is equivalent and avoids the waste.
        fetched_keys: set[tuple[str, SearchQuery]] = set()
        # With one fetch per enabled search the same unsupported-filter warning
        # repeats per search. It is deduped here — the warning is now per-search in
        # principle, but the recorded shapes (one warning per triple in
        # `errors_json`, the criteria_compile triples) must stay stable.
        seen_compile_warnings: set[tuple[str, str, str]] = set()
        seen_capability_errors: set[tuple[str, str]] = set()

        # Sequentially ACROSS searches, concurrently within one (one `gather` per
        # search). The order is deterministic and it is what fixes `first_seen_at` —
        # and so the Tier-2 earliest-seen survivor — when two sources return the
        # same listing.
        for _scoped_search_id, scoped_query in fetch_plan:
            adapters_for_query = [
                adapter
                for adapter in selected
                if (adapter.name, scoped_query) not in fetched_keys
            ]
            if not adapters_for_query:
                continue
            fetched_keys.update(
                (adapter.name, scoped_query) for adapter in adapters_for_query
            )
            batch = await _fetch_all(adapters_for_query, scoped_query)
            for result, capability_warnings, warning_records in batch:
                # A filter the board cannot honour is recorded, never silently
                # dropped (SRC-09/T-01-18). It is a warning, not a run failure: the
                # fetch itself may still be healthy. The same warnings also land in
                # the stage log below as structured triples (D-37 / T-02-19).
                for record in warning_records:
                    triple = (
                        str(record["source"]),
                        str(record["filter_name"]),
                        str(record["reason"]),
                    )
                    if triple not in seen_compile_warnings:
                        seen_compile_warnings.add(triple)
                        compile_warnings.append(record)
                for capability_warning in capability_warnings:
                    capability_key = (
                        str(capability_warning["source"]),
                        str(capability_warning["error"]),
                    )
                    if capability_key not in seen_capability_errors:
                        seen_capability_errors.add(capability_key)
                        errors.append(capability_warning)
                results.append(result)
                counts = await _persist_result(session_factory, result, resolved_run_id)
                if result.source in source_counts:
                    source_counts[result.source] = _merge_source_counts(
                        source_counts[result.source], counts
                    )
                else:
                    source_counts[result.source] = counts
                if result.status != "ok":
                    errors.append(
                        {
                            "source": result.source,
                            "status": result.status,
                            "error": result.error,
                        }
                    )

        # Exactly one `persist:<source>` entry per source, carrying the MERGED
        # counts — never one per search. The stage names and entry shape are pinned
        # by the run detail UI and the 02-* tests.
        for source_name, counts in source_counts.items():
            stage_log.append(_stage_entry(f"persist:{source_name}", counts, []))
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
            filter_result = await run_filter_stage(
                session_factory, resolved_run_id, search_id=search_id
            )
            excluded_count = int(filter_result.counts.get("excluded_listings", 0))
            stage_log.append(_stage_entry(FILTER_STAGE, filter_result.counts, filter_result.errors))
            errors.extend(
                {"source": FILTER_STAGE, "status": "warning", "error": message}
                for message in filter_result.errors
            )
        except Exception as exc:  # noqa: BLE001 — the filter must not sink a saved run
            log.exception("pipeline.filter_failed", run_id=resolved_run_id, error=str(exc))
            errors.append({"source": FILTER_STAGE, "status": "failed", "error": str(exc)})

        # Ranking (D-87 / D-88): after the hard filter and before `_finish`. The
        # stage is DETACHED — the run completes normally first (D-88) and the task
        # scores survivors one at a time, so it is never kept open. Best-effort like
        # dedup and filter: a failure to start is recorded and the run still
        # finishes. The survivors are resolved to decide whether starting is worth
        # it at all; `run_ranking` resolves its own list once it runs.
        try:
            async with session_factory() as session:
                candidates = await active_listings(session, run_id=resolved_run_id)
                excluded_ids = await rule_counts_for_listings(
                    session, run_id=resolved_run_id
                )
            if any(record.id not in excluded_ids for record in candidates):
                start_ranking_task(
                    resolved_run_id,
                    session_factory,
                    llm=backend,
                    search_id=search_id,
                )
        except Exception as exc:  # noqa: BLE001 — a ranking-start failure must not sink the run
            log.exception("pipeline.rank_start_failed", run_id=resolved_run_id, error=str(exc))
            errors.append({"source": RANK_STAGE, "status": "failed", "error": str(exc)})
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

    # The run's reason (RUN-03 / D-44): assembled after the filter stage from what
    # the run already knows, decided by the pure `compute_empty_reason`, and written
    # for every run — a thin queue and a healthy one both need to explain themselves.
    reason, reason_counts = await _assemble_run_reason(
        session_factory,
        resolved_run_id,
        adapters_resolved=adapters_resolved,
        source_counts=source_counts,
        capability_warnings=compile_warnings,
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
        reason=reason,
        reason_counts=reason_counts,
    )
    # Every search this run actually fetched records its freshness: the global run
    # now fetches each enabled search's criteria, so a blank "last run" line on
    # `/searches` would be a false signal that the run ignored them. An explicit
    # query and the zero-enabled `default_query()` fallback stamp nothing.
    await _stamp_last_run(session_factory, stamped_search_ids)
    log.info(
        "pipeline.finished",
        run_id=resolved_run_id,
        trigger=trigger,
        status=status,
        reason=reason,
        sources=sorted(source_counts),
    )
    return resolved_run_id


__all__ = [
    "MANUAL",
    "NO_SOURCES_REASON",
    "TERMINAL_STATUSES",
    "build_budget",
    "default_query",
    "resolve_enabled_adapters",
    "run_pipeline",
]
