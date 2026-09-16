"""RUN-03 / D-44 — the run's reason is deterministic, ordered and never ambiguous.

PITFALLS P9: "the queue is empty and `runs` shows a successful run, with no
per-source counts or exclusion reasons to explain it" is the top warning sign. This
lane pins the precedence order branch by branch, the adjacency pairs where a naive
implementation picks the wrong cause, and the totality of the boundary cases.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from app.domain.run_reason import REASONS, RunCounts, compute_empty_reason, reason_sentence

MODULE_PATH = Path(__file__).resolve().parents[2] / "app" / "domain" / "run_reason.py"

#: The six values exactly as the plan fixes them, in precedence order.
EXPECTED_REASONS = (
    "no_sources_enabled",
    "all_sources_failed",
    "zero_fetched",
    "all_filtered",
    "nothing_new",
    "mixed",
)


# --- the enum itself -----------------------------------------------------------


def test_the_reason_enum_is_exactly_the_six_documented_values_in_precedence_order() -> None:
    assert REASONS == EXPECTED_REASONS


def test_all_public_symbols_are_exported() -> None:
    import app.domain.run_reason as module

    assert set(module.__all__) == {
        "REASONS",
        "RunCounts",
        "compute_empty_reason",
        "reason_sentence",
    }


def test_the_module_imports_no_io_module() -> None:
    """Purity is a contract, not a convention: `app.domain` is I/O-free."""
    forbidden = {"httpx", "sqlalchemy", "jobspy", "jinja2", "subprocess", "fastapi"}
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            imported.add(node.module.split(".")[0])

    assert imported & forbidden == set()
    # It does not read settings either — the caller supplies the watermark.
    assert "app" not in imported, "run_reason must not depend on the application layer"


# --- one test per branch -------------------------------------------------------


def test_no_sources_enabled_when_no_adapter_resolved() -> None:
    assert compute_empty_reason(RunCounts()) == "no_sources_enabled"


def test_all_sources_failed_when_every_status_is_not_ok() -> None:
    counts = RunCounts(adapters_resolved=2, statuses=("blocked", "rate_limited"), fetched=0)

    assert compute_empty_reason(counts) == "all_sources_failed"


def test_all_sources_failed_does_not_fire_when_listings_were_fetched() -> None:
    """A merged non-`ok` status with listings fetched must not claim nothing came back.

    Two enabled searches on one source: one `ok` with listings, one `blocked`. The
    merged per-source status is `blocked`, but a listing was fetched and survives, so
    `all_sources_failed` (and its "fetched nothing" sentence) would be a false claim.
    """
    counts = RunCounts(
        adapters_resolved=1,
        statuses=("blocked",),
        fetched=1,
        excluded_by_rule={},
        survivors=1,
        new_since_watermark=1,
    )

    reason = compute_empty_reason(counts)

    assert reason != "all_sources_failed"
    assert reason == "mixed", "a failed-and-fetched run is a co-occurrence, not a total failure"
    assert "fetched nothing" not in reason_sentence(reason, counts)


def test_all_sources_failed_still_fires_when_every_source_failed_and_nothing_was_fetched() -> None:
    """The guard case: the rule must still exist when the failure really cost the run."""
    counts = RunCounts(adapters_resolved=2, statuses=("blocked", "error"), fetched=0)

    assert compute_empty_reason(counts) == "all_sources_failed"
    assert reason_sentence("all_sources_failed", counts) == (
        "All 2 sources failed, so the run fetched nothing."
    )


def test_zero_fetched_when_every_status_is_ok_and_nothing_came_back() -> None:
    counts = RunCounts(adapters_resolved=2, statuses=("ok", "ok"), fetched=0)

    assert compute_empty_reason(counts) == "zero_fetched"


def test_all_filtered_when_a_rule_fired_and_nothing_survived() -> None:
    counts = RunCounts(
        adapters_resolved=1,
        statuses=("ok",),
        fetched=3,
        excluded_by_rule={"7": 3},
        survivors=0,
    )

    assert compute_empty_reason(counts) == "all_filtered"


def test_nothing_new_when_survivors_all_predate_the_watermark() -> None:
    counts = RunCounts(
        adapters_resolved=1,
        statuses=("ok",),
        fetched=3,
        excluded_by_rule={},
        survivors=3,
        new_since_watermark=0,
    )

    assert compute_empty_reason(counts) == "nothing_new"


def test_mixed_when_a_co_occurrence_no_branch_claims() -> None:
    counts = RunCounts(
        adapters_resolved=2,
        statuses=("ok", "error"),
        fetched=3,
        excluded_by_rule={"7": 1},
        survivors=2,
        new_since_watermark=2,
    )

    assert compute_empty_reason(counts) == "mixed"


# --- precedence and adjacency --------------------------------------------------


def test_no_sources_enabled_wins_over_every_other_cause() -> None:
    """A run that resolved nothing did not fail, fetch nothing, or filter anything."""
    counts = RunCounts(
        adapters_resolved=0,
        statuses=("ok", "blocked"),
        fetched=9,
        excluded_by_rule={"7": 9},
        survivors=0,
        new_since_watermark=0,
    )

    assert compute_empty_reason(counts) == "no_sources_enabled"


def test_all_sources_failed_wins_over_zero_fetched_when_sources_failed() -> None:
    """Both are true (0 fetched); the failure is the cause worth reporting."""
    counts = RunCounts(adapters_resolved=2, statuses=("blocked", "error"), fetched=0)

    assert compute_empty_reason(counts) == "all_sources_failed"


def test_zero_fetched_wins_over_all_filtered_when_nothing_was_fetched() -> None:
    """An empty fetched set can never be explained as "everything was filtered"."""
    counts = RunCounts(
        adapters_resolved=2,
        statuses=("ok", "ok"),
        fetched=0,
        excluded_by_rule={"7": 3},
        survivors=0,
    )

    assert compute_empty_reason(counts) == "zero_fetched"


def test_all_filtered_wins_over_nothing_new_when_there_are_no_survivors() -> None:
    """`nothing_new` requires survivors; with none, the filter is the cause."""
    counts = RunCounts(
        adapters_resolved=1,
        statuses=("ok",),
        fetched=5,
        excluded_by_rule={"7": 5},
        survivors=0,
        new_since_watermark=0,
    )

    assert compute_empty_reason(counts) == "all_filtered"


def test_a_fired_rule_alone_is_not_all_filtered_while_survivors_remain() -> None:
    """The `survivors == 0` half of the all_filtered condition is load-bearing."""
    counts = RunCounts(
        adapters_resolved=1,
        statuses=("ok",),
        fetched=3,
        excluded_by_rule={"7": 1},
        survivors=2,
        new_since_watermark=2,
    )

    assert compute_empty_reason(counts) == "mixed"


# --- empty / boundary cases ----------------------------------------------------


def test_an_all_zero_counts_object_is_the_empty_corpus_boundary() -> None:
    counts = RunCounts(
        adapters_resolved=0,
        statuses=(),
        fetched=0,
        excluded_by_rule={},
        survivors=0,
        new_since_watermark=0,
    )

    assert compute_empty_reason(counts) == "no_sources_enabled"


def test_an_empty_status_list_with_resolved_adapters_does_not_raise_or_claim_failure() -> None:
    """No status is no evidence: claiming `all_sources_failed` here would be a lie."""
    counts = RunCounts(adapters_resolved=2, statuses=(), fetched=0)

    reason = compute_empty_reason(counts)

    assert reason in REASONS
    assert reason != "all_sources_failed"


def test_no_survivors_and_no_exclusions_is_not_all_filtered() -> None:
    """`all_filtered` needs a fired rule; an empty queue with none is `mixed`."""
    counts = RunCounts(adapters_resolved=1, statuses=("ok",), fetched=2, survivors=0)

    assert compute_empty_reason(counts) == "mixed"


def test_survivors_that_are_all_new_are_not_nothing_new() -> None:
    """`nothing_new` requires `new_since_watermark == 0`."""
    counts = RunCounts(
        adapters_resolved=1, statuses=("ok",), fetched=2, survivors=2, new_since_watermark=2
    )

    assert compute_empty_reason(counts) == "mixed"


# --- ordering / stability ------------------------------------------------------


def test_the_same_counts_evaluate_to_the_same_reason_twice() -> None:
    counts = RunCounts(
        adapters_resolved=2,
        statuses=("ok", "blocked"),
        fetched=4,
        survivors=1,
        new_since_watermark=1,
    )

    assert compute_empty_reason(counts) == compute_empty_reason(counts)


def test_every_reachable_reason_is_a_member_of_the_enum() -> None:
    matrix = [
        RunCounts(),
        RunCounts(adapters_resolved=1, statuses=("error",)),
        RunCounts(adapters_resolved=1, statuses=("ok",)),
        RunCounts(adapters_resolved=1, statuses=("ok",), fetched=1, excluded_by_rule={"7": 1}),
        RunCounts(adapters_resolved=1, statuses=("ok",), fetched=1, survivors=1),
        RunCounts(
            adapters_resolved=1,
            statuses=("ok", "error"),
            fetched=1,
            excluded_by_rule={"7": 1},
            survivors=1,
            new_since_watermark=1,
        ),
    ]

    produced = {compute_empty_reason(counts) for counts in matrix}

    assert produced <= set(REASONS)
    assert produced == set(REASONS), "every branch must be reachable from real counts"


# --- precision -----------------------------------------------------------------


def test_the_sentence_renders_integer_counts_without_floating_point_formatting() -> None:
    counts = RunCounts(
        adapters_resolved=2,
        statuses=("ok", "ok"),
        fetched=10,
        excluded_by_rule={"7": 10},
        survivors=0,
        new_since_watermark=0,
    )

    sentence = reason_sentence("all_filtered", counts)

    total_excluded = sum(counts.excluded_by_rule.values())
    assert isinstance(counts.fetched, int)
    assert isinstance(counts.survivors, int)
    assert isinstance(total_excluded, int)
    assert isinstance(counts.adapters_resolved, int)
    assert str(counts.fetched) in sentence
    assert str(total_excluded) in sentence
    assert re.search(r"\d+\.\d+", sentence) is None, (
        "a float-formatted count leaked into the sentence"
    )


def test_no_sentence_for_any_reason_contains_a_float_formatted_number() -> None:
    counts = RunCounts(
        adapters_resolved=3,
        statuses=("ok", "ok", "error"),
        fetched=7,
        excluded_by_rule={"7": 2, "9": 1},
        survivors=4,
        new_since_watermark=4,
    )

    for reason in REASONS:
        assert re.search(r"\d+\.\d+", reason_sentence(reason, counts)) is None


# --- the sentence is derived, never stored -------------------------------------


def test_all_filtered_sentence_names_the_exclusion_count() -> None:
    counts = RunCounts(
        adapters_resolved=1,
        statuses=("ok",),
        fetched=4,
        excluded_by_rule={"7": 4},
        survivors=0,
    )

    sentence = reason_sentence("all_filtered", counts)

    assert str(4) in sentence
    assert "exclusion" in sentence


def test_nothing_new_sentence_says_nothing_is_new() -> None:
    counts = RunCounts(
        adapters_resolved=1,
        statuses=("ok",),
        fetched=4,
        excluded_by_rule={},
        survivors=4,
        new_since_watermark=0,
    )

    sentence = reason_sentence("nothing_new", counts)

    assert "0 are new" in sentence
    assert str(counts.survivors) in sentence


def test_the_sentence_changes_when_a_count_changes() -> None:
    """Derived from the counts: the same reason with different numbers reads differently."""
    few = RunCounts(adapters_resolved=1, statuses=("ok",), fetched=2, excluded_by_rule={"7": 2})
    many = RunCounts(adapters_resolved=1, statuses=("ok",), fetched=40, excluded_by_rule={"7": 40})

    assert reason_sentence("all_filtered", few) != reason_sentence("all_filtered", many)
    assert "2" in reason_sentence("all_filtered", few)
    assert "40" in reason_sentence("all_filtered", many)


def test_every_reason_renders_a_non_empty_sentence() -> None:
    counts = RunCounts(adapters_resolved=2, statuses=("ok", "ok"), fetched=5, survivors=5)

    for reason in REASONS:
        sentence = reason_sentence(reason, counts)
        assert isinstance(sentence, str) and sentence.strip()
