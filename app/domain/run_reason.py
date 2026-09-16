"""The run's reason: a deterministic enum over integer counts (RUN-03 / D-44).

A zero-result run must never be ambiguous (PITFALLS P9). "The queue is empty and
`runs` shows a successful run" is the top warning sign this module exists to
remove: every run persists one reason drawn from a **fixed, documented precedence
order**, plus the integer counts behind it, so a human can always answer "why is
this not in my queue?" months later without re-running anything.

Pure: standard library only, no I/O, no `Settings`, no LLM. The caller assembles
`RunCounts` from what the run already knows and passes the watermark in — this
module never reads the database and never advances the watermark (plan 02-07 owns
the queue-open behaviour).

Pattern 4 — persist the decomposition, compute the aggregate: the reason is the
aggregate and `RunCounts` is the decomposition. `reason_sentence()` renders *from*
the counts and is deliberately never stored as the only artifact; a stored sentence
would drift from its numbers the moment anything was rendered differently.

`no_sources_enabled` recognises the **same** condition
`app.pipeline.run.NO_SOURCES_REASON` describes ("no enabled sources resolved from
the adapter registry"). It is a recognition, not a second vocabulary: the string
lives in exactly one place and the enum value is its machine-readable name.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

#: The reason enum, in **precedence order**. The first matching cause wins; the
#: order is the contract and is asserted branch by branch. Mirrored by the named
#: `ck_runs_reason` CHECK added in migration 0002, so widening this later is a
#: coordinated migration plus a UI change — keep this the single in-code source.
REASONS: tuple[str, ...] = (
    "no_sources_enabled",
    "all_sources_failed",
    "zero_fetched",
    "all_filtered",
    "nothing_new",
    "mixed",
)

#: The status a source reports when it ran to completion. A source that did not
#: report `ok` degrades the run but does not by itself empty the queue.
_OK_STATUS = "ok"


@dataclass(frozen=True)
class RunCounts:
    """The decomposition behind a run's reason — every value an integer or a fact.

    `statuses` is one status per resolved source (the resolved count is
    `adapters_resolved`, which is a *different* number: it counts adapters, while a
    source that failed to persist still reports a status). `excluded_by_rule` maps
    `rule_id` to that rule's firing count for this run — non-empty means at least
    one rule fired, which is what makes `all_filtered` decidable.
    """

    adapters_resolved: int = 0
    statuses: tuple[str, ...] = ()
    fetched: int = 0
    excluded_by_rule: Mapping[str, int] = field(default_factory=dict)
    survivors: int = 0
    new_since_watermark: int = 0


def _statuses(counts: RunCounts) -> tuple[str, ...]:
    """The statuses as a tuple, tolerating an absent (or empty) status list."""
    return tuple(str(status) for status in (counts.statuses or ()))


def _total_excluded(counts: RunCounts) -> int:
    """The number of exclusions this run recorded, summed over rules."""
    return sum(int(value) for value in (counts.excluded_by_rule or {}).values())


def compute_empty_reason(counts: RunCounts) -> str:
    """The reason for this run's outcome, first match wins.

    1. `no_sources_enabled` — no adapter resolved at all. This recognises the same
       condition `NO_SOURCES_REASON` describes; no second vocabulary is minted.
    2. `all_sources_failed` — at least one source reported a status, **every** one
       of them reported a non-`ok` status, **and nothing was fetched**. A status list
       is required: with no statuses at all there is no evidence a source failed, and
       claiming `all_sources_failed` would be a lie (P9). The `fetched == 0` guard is
       required for the union run: a source fetched once per enabled search reports
       the worst status, so one search can come back `ok` with listings while another
       is `blocked` — the merged status is then non-`ok`, but listings exist and
       survive, so "all sources failed, the run fetched nothing" is factually false.
       This is evaluated on the *merged* per-source status the caller records; the
       guard makes the rule fire only when that failure actually cost the run its
       listings.
    3. `zero_fetched` — every source was `ok` and the run still fetched nothing.
    4. `all_filtered` — something was fetched, at least one rule fired
       (`excluded_by_rule` is non-empty, so exclusions were actually recorded), and
       **no** listing survived. Requires `survivors == 0`: a non-empty
       `excluded_by_rule` alone only proves *some* rule fired, not that nothing got
       through.
    5. `nothing_new` — listings survived the rules but every one of them predates
       the watermark, so the queue gained nothing. Requires `survivors > 0` and
       `new_since_watermark == 0`.
    6. `mixed` — anything else: a co-occurrence no earlier branch claims (two or
       more causes at once, or a case with too little evidence to name one cause).
    """
    # 1 — the empty-corpus boundary: nothing resolved, so nothing could run.
    if int(counts.adapters_resolved) <= 0:
        return "no_sources_enabled"

    statuses = _statuses(counts)

    # 2 — every source that reported failed AND the run fetched nothing. Without the
    # `fetched` guard a union run whose per-source status merges to non-`ok` (one
    # search `blocked`, another `ok` with listings) would claim nothing was fetched.
    if (
        statuses
        and all(status != _OK_STATUS for status in statuses)
        and int(counts.fetched) <= 0
    ):
        return "all_sources_failed"

    # 3 — all healthy, nothing returned.
    if (
        statuses
        and all(status == _OK_STATUS for status in statuses)
        and int(counts.fetched) <= 0
    ):
        return "zero_fetched"

    # 4 — fetched something, a rule fired, nothing survived.
    if int(counts.fetched) > 0 and _total_excluded(counts) > 0 and int(counts.survivors) <= 0:
        return "all_filtered"

    # 5 — survivors exist but none is new since the queue was last opened.
    if int(counts.survivors) > 0 and int(counts.new_since_watermark) <= 0:
        return "nothing_new"

    # 6 — a co-occurrence no branch above claims.
    return "mixed"


def reason_sentence(reason: str, counts: RunCounts) -> str:
    """A short human sentence rendered **from** the counts (Pattern 4).

    The sentence states the numbers it used, so a changed count changes the
    sentence. It is never the only artifact: `reason_counts_json` carries the
    decomposition and this is computed at render time.
    """
    statuses = len(_statuses(counts))
    fetched = int(counts.fetched)
    survivors = int(counts.survivors)
    excluded = _total_excluded(counts)
    exclusion_word = "exclusion" if excluded == 1 else "exclusions"

    if reason == "no_sources_enabled":
        return (
            f"No sources are enabled, so the run fetched nothing "
            f"({int(counts.adapters_resolved)} adapters resolved)."
        )
    if reason == "all_sources_failed":
        return f"All {statuses} sources failed, so the run fetched nothing."
    if reason == "zero_fetched":
        return f"{statuses} sources responded ok but returned 0 listings."
    if reason == "all_filtered":
        return (
            f"All {fetched} fetched listings were rejected by the rules "
            f"({excluded} {exclusion_word} recorded)."
        )
    if reason == "nothing_new":
        return (
            f"{survivors} listings survived the rules but 0 are new since the queue "
            f"was last opened."
        )
    return (
        f"{survivors} listings survived the rules out of {fetched} fetched; "
        f"{excluded} {exclusion_word} were recorded."
    )


__all__ = [
    "REASONS",
    "RunCounts",
    "compute_empty_reason",
    "reason_sentence",
]
