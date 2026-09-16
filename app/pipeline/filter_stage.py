"""The deterministic hard-filter stage (FILT-01/02): rules reject before any LLM call.

Ordering is fixed by `ARCHITECTURE.md` §8.1: fetch -> sanitise -> normalise ->
**dedup/merge** -> **hard-rule filter** -> cap. This stage therefore runs after the
dedup stage and before `_finish`; filtering before merging would discard the copy
that carried the salary (RESEARCH anti-pattern AP4).

This path makes **no model call** — it imports no LLM module and writes no
`llm_calls` row. Every decision is a pure function from `app.domain.filter`.

Rule scope is the **union of every enabled search** (A4): rules are loaded from all
enabled searches and a listing rejected by any one of them leaves the queue.

The stage is total (PITFALLS P10): one malformed rule or one bad listing is caught,
recorded on `StageCounts` and logged, and the rest of the run proceeds. A skipped
rule is counted so it is visible rather than silently treated as applied.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Run
from app.db.repositories.exclusion_repo import record_exclusions
from app.db.repositories.search_repo import (
    active_listings,
    enabled_searches,
    rules_for_searches,
)
from app.domain.criteria import rule_specs_from
from app.domain.filter import evaluate
from app.pipeline.stages import StageCounts, StageResult

log = structlog.get_logger(__name__)

FILTER_STAGE = "filter"


async def run_filter_stage(
    session_factory: async_sessionmaker[AsyncSession],
    run_id: int,
    *,
    now: datetime | None = None,
) -> StageResult:
    """Evaluate this run's rules against every listing the run touched.

    Returns a `StageResult` whose counts carry `survivors`, `excluded_listings` and
    `exclusions`; `run_pipeline` turns `excluded_listings` into `filtered_count`.
    """
    counts = StageCounts()
    moment = now or datetime.now(UTC)

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None or run.started_at is None:
            return StageResult(FILTER_STAGE, counts.counts, counts.errors)

        searches = await enabled_searches(session)
        counts.bump("enabled_searches", len(searches))
        if not searches:
            # No enabled search means no rules: the stage is legitimately a no-op.
            # This is NOT the same condition as `no_sources_enabled` — an enabled
            # search with no rules is valid and filters nothing.
            return StageResult(FILTER_STAGE, counts.counts, counts.errors)

        version_by_search = {record.id: record.version for record in searches}
        rules = await rules_for_searches(session, [record.id for record in searches])
        specs = rule_specs_from([record.as_mapping() for record in rules])

        # A rule the assembler dropped (an unknown `kind` from a row written before
        # a vocabulary change, or a row with no usable identifier) is counted, never
        # silently treated as applied. Normally zero: the plan-02-01 CHECK and the
        # repository's enabled filter already rule those rows out.
        if len(rules) != len(specs):
            counts.bump("rules_skipped", len(rules) - len(specs))
        counts.bump("rules_loaded", len(specs))

        # rule_id -> the search that owns it, for the exclusion's criteria_version.
        search_id_by_rule = {record.rule_id: record.search_id for record in rules}

        listings = await active_listings(session, run_id=run_id)
        counts.bump("candidates", len(listings))

        for record in listings:
            try:
                outcomes = evaluate(specs, record.as_facts())
            except Exception as exc:  # noqa: BLE001 — one bad listing must not abort
                counts.fail(f"filter failed for listing {record.id}: {type(exc).__name__}")
                log.warning(
                    "pipeline.filter_listing_failed",
                    run_id=run_id,
                    listing_id=record.id,
                    error=type(exc).__name__,
                )
                continue

            if not outcomes:
                counts.bump("survivors")
                continue

            # A listing may be rejected by rules from more than one search (the
            # union scope). The row records the version of the search owning the
            # FIRST firing rule — deterministic, because `evaluate` orders by
            # `(position, rule_id)` and a rule id belongs to exactly one search.
            first = outcomes[0]
            owning_search = search_id_by_rule.get(first.rule_id)
            criteria_version = version_by_search.get(owning_search) if owning_search else None

            try:
                written = await record_exclusions(
                    session,
                    listing_id=record.id,
                    run_id=run_id,
                    outcomes=outcomes,
                    criteria_version=criteria_version,
                    now=moment,
                )
            except Exception as exc:  # noqa: BLE001 — one bad write must not abort
                counts.fail(f"exclusion write failed for listing {record.id}: {type(exc).__name__}")
                log.warning(
                    "pipeline.exclusion_write_failed",
                    run_id=run_id,
                    listing_id=record.id,
                    error=type(exc).__name__,
                )
                continue

            counts.bump("excluded_listings")
            counts.bump("exclusions", written)

        await session.commit()

    return StageResult(FILTER_STAGE, counts.counts, counts.errors)


__all__ = ["FILTER_STAGE", "run_filter_stage"]
