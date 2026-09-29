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
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Run
from app.db.repositories.exclusion_repo import record_exclusions
from app.db.repositories.search_repo import (
    active_listings,
    enabled_searches,
    rules_for_searches,
    search_by_id,
)
from app.domain.criteria import rule_specs_from, search_query_from, work_mode_from
from app.domain.filter import RuleSpec, evaluate
from app.pipeline.stages import StageCounts, StageResult

log = structlog.get_logger(__name__)

FILTER_STAGE = "filter"

#: Implicit rule ids are prefixed so they can never collide with a `filter_rules.id`
#: (a decimal string). The id names the search and the criterion it belongs to, so
#: the persisted exclusion's `criteria_version` can be resolved from the same map as
#: a DB rule.
_IMPLICIT_RULE = "search:{search_id}:{criterion}"


def _implicit_rules_for_search(record: Any) -> list[RuleSpec]:
    """The in-memory hard rules a search's own fetch-side criteria imply.

    Two of a search's criteria are fetch-side intent the boards cannot express, so
    without these they silently filter nothing. Both reuse the existing pure
    evaluators through `evaluate()` — no second predicate exists:

    * `seniority` -> the `_eval_seniority` allow-list (`unknown_passes=True`);
    * `work_mode` `remote`/`onsite` -> the `_eval_remote` flag check. Only the
      normalise stage's `remote_flag` can prove a mode, so an unknown flag passes.
      `hybrid` deliberately produces NO rule: nothing in the data carries a hybrid
      signal, and it is a ranking hint (see `app.pipeline.rank`).
    """
    criteria = record.criteria_json
    search_id = record.id
    specs: list[RuleSpec] = []

    seniority = search_query_from(criteria).seniority
    if seniority:
        specs.append(
            RuleSpec(
                rule_id=_IMPLICIT_RULE.format(search_id=search_id, criterion="seniority"),
                kind="seniority",
                params={"allow": list(seniority), "unknown_passes": True},
                position=0,
            )
        )

    work_mode = work_mode_from(criteria)
    if work_mode in ("remote", "onsite"):
        specs.append(
            RuleSpec(
                rule_id=_IMPLICIT_RULE.format(search_id=search_id, criterion="work_mode"),
                kind="remote",
                # `_eval_remote` fires when the listing's flag EQUALS `flag`, so
                # `flag` is the flag this mode excludes: `remote` excludes a
                # non-remote listing (False); `onsite` excludes a remote one (True).
                # `None` equals neither, so an unknown passes.
                params={"require": True, "flag": work_mode == "onsite"},
                position=0,
            )
        )

    return specs


def _implicit_rules(searches: list) -> list[tuple[int, RuleSpec]]:
    """Every search's implicit hard rules, paired with the owning search's id."""
    rules: list[tuple[int, RuleSpec]] = []
    for record in searches:
        rules.extend(
            (record.id, spec) for spec in _implicit_rules_for_search(record)
        )
    return rules


async def run_filter_stage(
    session_factory: async_sessionmaker[AsyncSession],
    run_id: int,
    *,
    search_id: int | None = None,
    now: datetime | None = None,
) -> StageResult:
    """Evaluate this run's rules against every listing the run touched.

    Rule scope is the **union of every enabled search** (A4) when `search_id` is
    `None`. A per-search run (`search_id` not `None`, D-45's "Run this one") scopes
    to that one search — enabled or not, because the user pointed at it explicitly —
    so iterating on a single search cannot be perturbed by another search's rules.

    Returns a `StageResult` whose counts carry `survivors`, `excluded_listings` and
    `exclusions`; `run_pipeline` turns `excluded_listings` into `filtered_count`.
    """
    counts = StageCounts()
    moment = now or datetime.now(UTC)

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None or run.started_at is None:
            return StageResult(FILTER_STAGE, counts.counts, counts.errors)

        if search_id is not None:
            scoped = await search_by_id(session, search_id)
            searches = [scoped] if scoped is not None else []
        else:
            searches = await enabled_searches(session)
        counts.bump("enabled_searches", len(searches))
        if not searches:
            # No enabled search means no rules: the stage is legitimately a no-op.
            # This is NOT the same condition as `no_sources_enabled` — an enabled
            # search with no rules is valid and filters nothing.
            return StageResult(FILTER_STAGE, counts.counts, counts.errors)

        version_by_search = {record.id: record.version for record in searches}
        rules = await rules_for_searches(session, [record.id for record in searches])
        db_specs = rule_specs_from([record.as_mapping() for record in rules])

        # A rule the assembler dropped (an unknown `kind` from a row written before
        # a vocabulary change, or a row with no usable identifier) is counted, never
        # silently treated as applied. Normally zero: the plan-02-01 CHECK and the
        # repository's enabled filter already rule those rows out.
        if len(rules) != len(db_specs):
            counts.bump("rules_skipped", len(rules) - len(db_specs))

        # Each enabled search's own fetch-side criteria are IMPLICIT rules. They are
        # evaluated through the same pure evaluators as a stored rule, so a listing
        # whose known value is excluded by the criterion is dropped and an unknown
        # passes. This is what makes the existing saved criteria work with no
        # re-save and no migration.
        implicit_rules = _implicit_rules(searches)
        counts.bump("implicit_rules", len(implicit_rules))
        specs = db_specs + [spec for _search_id, spec in implicit_rules]
        counts.bump("rules_loaded", len(specs))

        # rule_id -> the search that owns it, for the exclusion's criteria_version.
        # Implicit rules carry a synthetic id, so they are added to the same map.
        search_id_by_rule = {record.rule_id: record.search_id for record in rules}
        search_id_by_rule.update(
            {spec.rule_id: search_id for search_id, spec in implicit_rules}
        )

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
            # union scope), so each row records the version of ITS OWN owning
            # search rather than the first firing rule's. `evaluate` orders by
            # `(position, rule_id)` and a rule id belongs to exactly one search.
            version_by_rule = {
                outcome.rule_id: version_by_search.get(search_id_by_rule.get(outcome.rule_id))
                for outcome in outcomes
                if outcome.rule_id is not None
            }

            try:
                written = await record_exclusions(
                    session,
                    listing_id=record.id,
                    run_id=run_id,
                    outcomes=outcomes,
                    version_by_rule=version_by_rule,
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
