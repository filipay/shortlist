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

from app.config import (
    KNOWN_FORCED_TOOL_CHOICE_INCOMPATIBLE_MODELS,
    Settings,
    settings,
)
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
    # Phase 3 (PLAT-04 applied to PLAT-02): the opencode completion budget.
    "opencode_completion_timeout_seconds",
    "opencode_max_retries",
    "opencode_structured_retry_count",
    # The model a schema-constrained call resolves by default: a configuration
    # fact whose shipped value this task moves, so the surface guard covers it.
    "opencode_model",
    # A pre-existing LIMIT_FIELDS entry the surface guard had omitted; covered here
    # so "every LIMIT_FIELDS name is a required field" actually holds.
    "probe_cache_ttl_seconds",
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
    # Phase 3 (PLAT-04 applied to PLAT-02). Both are small integers BELOW
    # DISTINCTIVE_THRESHOLD_FLOOR, so they add nothing to the literal scan; listing
    # them keeps the "what counts as a ceiling" set complete. The completion
    # timeout is a FLOAT and is a deliberately separate field from
    # `opencode_timeout_seconds` (Pitfall P4) — do not merge them.
    "opencode_max_retries",
    "opencode_structured_retry_count",
)

#: The Phase-3 ceilings (PLAT-04 applied to PLAT-02), listed explicitly so a future
#: edit that drops one from either guard below fails loudly rather than silently
#: un-covering it.
#:
#: The completion ceiling is deliberately a SEPARATE field from
#: `opencode_timeout_seconds`, which stays scoped to health/discovery (Pitfall P4):
#: a real structured completion is a different order of magnitude, so do not
#: "simplify" the two back into one field.
PHASE_THREE_CEILINGS = (
    "opencode_completion_timeout_seconds",
    "opencode_max_retries",
    "opencode_structured_retry_count",
)

#: The Phase-3 ceilings that are integers (the completion timeout is a float).
PHASE_THREE_INTEGER_CEILINGS = (
    "opencode_max_retries",
    "opencode_structured_retry_count",
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
    # The shipped model default must be a model that can honour a forced tool call.
    assert Settings.model_fields["opencode_model"].default == "minimax-m3"


def test_the_phase_three_ceilings_are_guarded() -> None:
    """Every Phase-3 ceiling must be asserted by the surface guard (PLAT-04)."""
    for field in PHASE_THREE_CEILINGS:
        assert field in REQUIRED_SETTINGS_FIELDS, (
            f"{field} is a Phase-3 ceiling but REQUIRED_SETTINGS_FIELDS omits it"
        )
    for field in PHASE_THREE_INTEGER_CEILINGS:
        assert field in LIMIT_FIELDS, (
            f"{field} is a numeric ceiling but LIMIT_FIELDS does not cover it"
        )


def test_every_limit_field_is_a_required_numeric_ceiling() -> None:
    """A ceiling the surface guard does not assert is a knob nobody checks."""
    for field in LIMIT_FIELDS:
        assert field in REQUIRED_SETTINGS_FIELDS, (
            f"{field} is in LIMIT_FIELDS but missing from REQUIRED_SETTINGS_FIELDS"
        )
        default = Settings.model_fields[field].default
        assert isinstance(default, (int, float)) and not isinstance(default, bool), (
            f"{field} is listed as a ceiling but its default is {default!r}"
        )


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


def test_the_phase_three_ceilings_are_environment_tunable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A config field no test can override is only half a config field."""
    assert Settings.model_fields["opencode_completion_timeout_seconds"].default == 120.0
    assert Settings.model_fields["opencode_max_retries"].default == 2
    assert Settings.model_fields["opencode_structured_retry_count"].default == 2

    monkeypatch.setenv("OPENCODE_COMPLETION_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setenv("OPENCODE_MAX_RETRIES", "5")
    monkeypatch.setenv("OPENCODE_STRUCTURED_RETRY_COUNT", "4")

    refreshed = Settings()

    assert refreshed.opencode_completion_timeout_seconds == 7.5
    assert refreshed.opencode_max_retries == 5
    assert refreshed.opencode_structured_retry_count == 4


def test_the_shipped_model_default_is_environment_tunable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A constructed `Settings()` is the correct read here — the override is the point."""
    monkeypatch.setenv("OPENCODE_MODEL", "glm-5.3")

    assert Settings().opencode_model == "glm-5.3"


# --- the shipped model default must be able to satisfy a forced tool call ------


def test_the_default_model_is_not_a_known_forced_tool_call_incompatible_model() -> None:
    """The guard reads the DECLARED default, never an ambient-env-affected `Settings()`."""
    incompatible = KNOWN_FORCED_TOOL_CHOICE_INCOMPATIBLE_MODELS

    # A vacuous guard is not a guard: the set must name the evidenced counter-example.
    assert incompatible, "the incompatible-model set was emptied — the guard is vacuous"
    assert "deepseek-v4.1-flash" in incompatible

    declared = Settings.model_fields["opencode_model"].default
    assert declared not in incompatible, (
        f"the shipped opencode_model default {declared!r} is a model documented as "
        "unable to satisfy a forced tool call — it cannot make the schema-constrained "
        "call success criterion 1 requires"
    )


def test_the_compose_model_default_agrees_with_the_declared_one() -> None:
    """Three operator surfaces, one value: the expected spelling is DERIVED."""
    declared = str(Settings.model_fields["opencode_model"].default)

    compose = (PROJECT_ROOT / "compose.yml").read_text(encoding="utf-8")
    assert f"OPENCODE_MODEL=${{OPENCODE_MODEL:-{declared}}}" in compose, (
        "compose.yml's OPENCODE_MODEL passthrough default disagrees with the "
        "declared Settings default — a host without a .env would get a different model"
    )

    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    assert f"OPENCODE_MODEL={declared}" in env_example, (
        ".env.example's OPENCODE_MODEL value disagrees with the declared default"
    )


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
