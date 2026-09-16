"""The Tier-2 dedup stage (D-30): cross-source duplicates collapse after persist.

Post-persist by design: a cross-source candidate pair needs **both** rows to exist
before it can be scored, so the stage runs after every source's rows are persisted
and before `_finish`. The hard-filter stage (plan 02-05) inserts between this and
`_finish` — filtering before merging would discard the copy that carried the
salary (RESEARCH anti-pattern AP4).

θ and the posted window are read from `Settings` on every call — **no literal
appears in this module** (the distinctive-literal scan over `app/pipeline` in
`tests/test_config.py` enforces it).

The stage is total: one failing merge is caught, recorded on `StageCounts` and
logged, and the remaining merges still apply. A single bad pair must never abort a
run whose listings are already persisted.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import Listing, Run
from app.db.repositories.dupe_repo import (
    apply_merge,
    candidates_for_block,
    merged_pairs,
    reverted_pairs,
)
from app.domain.dedup import CandidateFacts, candidate_merges
from app.pipeline.stages import StageCounts, StageResult

log = structlog.get_logger(__name__)

DEDUP_STAGE = "dedup"


def _pair_text(facts: CandidateFacts) -> str:
    return " ".join(
        part
        for part in (facts.company_norm or "", facts.title_norm or "", facts.location_norm or "")
        if part
    )


async def run_dedup_stage(
    session_factory: async_sessionmaker[AsyncSession],
    run_id: int,
    *,
    now: datetime | None = None,
) -> StageResult:
    """Score this run's cross-source candidate pairs and apply the safe merges.

    Candidates are narrowed in two steps before any scoring: to the companies this
    run touched (`last_seen_at >= run.started_at`, the same window `source_repo`
    uses), then to one indexed `company_norm` block per company. No all-pairs
    comparison exists.
    """
    counts = StageCounts()
    moment = now or datetime.now(UTC)
    threshold = settings.dedup_fuzzy_threshold
    window = settings.dedup_posted_window_days

    async with session_factory() as session:
        run = await session.get(Run, run_id)
        if run is None or run.started_at is None:
            return StageResult(DEDUP_STAGE, counts.counts, counts.errors)

        company_norms = (
            (
                await session.execute(
                    select(Listing.company_norm)
                    .where(
                        Listing.is_active.is_(True),
                        Listing.company_norm.is_not(None),
                        Listing.last_seen_at >= run.started_at,
                    )
                    .distinct()
                )
            )
            .scalars()
            .all()
        )

        facts: list[CandidateFacts] = []
        for company_norm in sorted(name for name in company_norms if name):
            facts.extend(
                await candidates_for_block(
                    session, company_norm=company_norm, posted_window_days=window
                )
            )

        if not facts:
            counts.bump("candidates", 0)
            return StageResult(DEDUP_STAGE, counts.counts, counts.errors)

        counts.bump("candidates", len(facts))
        decisions = candidate_merges(facts, threshold=threshold, posted_window_days=window)
        counts.bump("proposed", len(decisions))
        if not decisions:
            return StageResult(DEDUP_STAGE, counts.counts, counts.errors)

        listing_ids = [item.listing_id for item in facts]
        # Two pre-checks before scoring: a reverted pair (the user's explicit undo,
        # D-28) and a pair already merged and not reverted. The second keeps a
        # re-run from re-proposing a correct merge and recording a spurious error.
        reverted = await reverted_pairs(session, listing_ids=listing_ids)
        already_merged = await merged_pairs(session, listing_ids=listing_ids)
        by_id = {item.listing_id: item for item in facts}

        diagnostic_max = 0.0
        for decision in decisions:
            pair = (decision.survivor_id, decision.absorbed_id)
            if pair in reverted:
                counts.bump("skipped_reverted")
                continue
            if pair in already_merged:
                counts.bump("skipped_already_merged")
                continue
            try:
                async with session.begin_nested():
                    await apply_merge(session, decision=decision, now=moment, run_id=run_id)
            except Exception as exc:  # noqa: BLE001 — one bad pair must not abort the run
                counts.fail(
                    f"merge failed for pair ({decision.survivor_id}, "
                    f"{decision.absorbed_id}): {type(exc).__name__}"
                )
                log.warning(
                    "pipeline.dedup_merge_failed",
                    run_id=run_id,
                    survivor_id=decision.survivor_id,
                    absorbed_id=decision.absorbed_id,
                    error=type(exc).__name__,
                )
                continue

            counts.bump("merges")
            # The token-set score is a DIAGNOSTIC only — it is never the gate (it
            # is subset-forgiving, so "Software Engineer" scores 100 against
            # "Senior Software Engineer"). One bounded integer, not a per-pair map,
            # so the stage log cannot grow with the corpus.
            left = by_id.get(decision.survivor_id)
            right = by_id.get(decision.absorbed_id)
            if left is not None and right is not None:
                diagnostic_max = max(
                    diagnostic_max, float(fuzz.token_set_ratio(_pair_text(left), _pair_text(right)))
                )

        if "merges" in counts.counts:
            counts.counts["token_set_diagnostic_max"] = int(round(diagnostic_max))

        await session.commit()

    return StageResult(DEDUP_STAGE, counts.counts, counts.errors)


__all__ = ["DEDUP_STAGE", "run_dedup_stage"]
