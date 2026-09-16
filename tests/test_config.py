"""PLAT-04 / T-01-28 — every limit, threshold, country and budget is configuration.

Three complementary controls, because a config requirement that is only asserted
by reading the class can be satisfied by a class nobody uses:

1. **Surface** — `Settings` exposes every documented knob with its documented
   default.
2. **Behaviour** — an environment override changes the effective value, and the
   pipeline's budget/query builders reflect a patched `Settings`; this is what
   makes the ban-risk envelope auditable instead of aspirational.
3. **Absence** — no distinctive threshold literal is left hard-coded in
   `app/probe` or `app/pipeline`.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.config import Settings, settings
from app.pipeline.run import build_budget, default_query

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SETTINGS_FIELDS = (
    "probe_max_results",
    "probe_max_requests",
    "probe_max_detail_fetches",
    "probe_deadline_seconds",
    "probe_results_wanted",
    "probe_country_indeed",
    "description_max_chars",
    "local_user_id",
    "database_url_async",
    "database_url_sync",
    # Phase 2 queue + dedup envelope (D-31 / D-40 / D-42).
    "dedup_fuzzy_threshold",
    "dedup_posted_window_days",
    "stale_after_days",
    "queue_page_size",
)

#: Fields whose value is a ceiling an operator may need to tune.
LIMIT_FIELDS = (
    "probe_max_results",
    "probe_max_requests",
    "probe_max_detail_fetches",
    "probe_deadline_seconds",
    "probe_results_wanted",
    "probe_cache_ttl_seconds",
    "description_max_chars",
    # Both are distinctive integers >= DISTINCTIVE_THRESHOLD_FLOOR, so listing
    # them here is what makes the absence scan actually cover them.
    "dedup_fuzzy_threshold",
    "queue_page_size",
)

#: Values below this are too common in ordinary code (counts, indexes, 0/1) to
#: attribute to a hard-coded threshold; the distinctive ceilings are still caught.
DISTINCTIVE_THRESHOLD_FLOOR = 3

#: Directories the absence check scans. `app/probe` arrives in plan 01-06.
SCANNED_DIRS = ("app/probe", "app/pipeline")


# --- 1. surface ---------------------------------------------------------------


def test_settings_exposes_every_documented_knob() -> None:
    for field in REQUIRED_SETTINGS_FIELDS:
        assert field in Settings.model_fields, f"Settings is missing {field}"


def test_documented_defaults() -> None:
    """Asserted against the declared defaults so an ambient env var cannot flake it."""
    assert Settings.model_fields["probe_country_indeed"].default == "ireland"
    assert Settings.model_fields["probe_max_detail_fetches"].default == 0
    assert Settings.model_fields["dedup_fuzzy_threshold"].default == 88


# --- 2. behaviour -------------------------------------------------------------


def test_an_environment_override_changes_the_effective_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROBE_MAX_RESULTS", "7")
    monkeypatch.setenv("PROBE_COUNTRY_INDEED", "spain")

    refreshed = Settings()

    assert refreshed.probe_max_results == 7
    assert refreshed.probe_country_indeed == "spain"


def test_the_new_queue_knobs_are_environment_tunable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Phase-2 thresholds are overridable exactly like the probe_* fields."""
    assert Settings.model_fields["stale_after_days"].default == 14
    assert Settings.model_fields["queue_page_size"].default == 25

    monkeypatch.setenv("STALE_AFTER_DAYS", "30")
    monkeypatch.setenv("DEDUP_FUZZY_THRESHOLD", "95")

    refreshed = Settings()

    assert refreshed.stale_after_days == 30
    assert refreshed.dedup_fuzzy_threshold == 95


def test_build_budget_reads_every_ceiling_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "probe_max_requests", 11)
    monkeypatch.setattr(settings, "probe_max_results", 22)
    monkeypatch.setattr(settings, "probe_max_detail_fetches", 33)
    monkeypatch.setattr(settings, "probe_deadline_seconds", 44)
    moment = datetime(2026, 1, 1, tzinfo=UTC)

    budget = build_budget(now=moment)

    assert budget.max_requests == 11
    assert budget.max_results == 22
    assert budget.max_detail_fetches == 33
    assert (budget.deadline - moment).total_seconds() == 44


def test_default_query_reads_its_location_and_count_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "probe_results_wanted", 9)
    monkeypatch.setattr(settings, "probe_query_location", "Cork")

    query = default_query()

    assert query.results_wanted == 9
    assert query.location == "Cork"


# --- 3. absence ---------------------------------------------------------------


def _distinctive_thresholds() -> set[int]:
    values: set[int] = set()
    for field in LIMIT_FIELDS:
        default = getattr(Settings(), field)
        if isinstance(default, int) and default >= DISTINCTIVE_THRESHOLD_FLOOR:
            values.add(int(default))
    return values


def test_no_distinctive_threshold_literal_remains_in_probe_or_pipeline() -> None:
    distinctive = _distinctive_thresholds()
    assert distinctive, "no distinctive threshold values were derived — scan is vacuous"

    scanned = 0
    offenders: dict[str, list[int]] = {}
    for relative in SCANNED_DIRS:
        directory = PROJECT_ROOT / relative
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            scanned += 1
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            found = sorted(
                {
                    node.value
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Constant)
                    and isinstance(node.value, int)
                    and not isinstance(node.value, bool)
                    and node.value in distinctive
                }
            )
            if found:
                offenders[str(path.relative_to(PROJECT_ROOT))] = found

    assert scanned > 0, "no modules were scanned — the guard is vacuous"
    assert offenders == {}, (
        "a threshold literal is hard-coded instead of read from Settings: "
        f"{offenders} (distinctive values scanned: {sorted(distinctive)})"
    )


def test_the_literal_scan_can_actually_fail() -> None:
    """A guard that cannot fail is not a guard."""
    sample = ast.parse("RESULTS_WANTED = 50  # a re-hard-coded ceiling")

    found = [
        node.value
        for node in ast.walk(sample)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and node.value in _distinctive_thresholds()
    ]

    assert 50 in found


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
