"""PLAT-04 / T-01-28 — every limit, threshold, country and budget is configuration.

Three complementary controls, because a config requirement that is only asserted
by reading the class can be satisfied by a class nobody uses:

1. **Surface** — `Settings` exposes every documented knob with its documented
   default.
2. **Behaviour** — an environment override changes the effective value, and the
   pipeline's budget/query builders reflect a patched `Settings`; this is what
   makes the ban-risk envelope auditable instead of aspirational.
3. **Absence** — no distinctive threshold literal is left hard-coded in
   `app/probe`, `app/pipeline`, `app/latex` or `app/cv`.
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
    # Phase 4 (PLAT-04): the LaTeX engine, its storage roots and the importer
    # bounds. `tex_import_max_depth` is deliberately listed here as a required
    # setting but NOT in LIMIT_FIELDS (see the asymmetry note on LIMIT_FIELDS).
    "latex_engine",
    "tectonic_binary",
    "tectonic_cache_dir",
    "tectonic_timeout_seconds",
    "tectonic_offline",
    "latex_xelatex_binary",
    "cv_dir",
    "artifacts_dir",
    "tex_import_max_lines",
    "tex_import_max_depth",
    # Phase 4 (WR-03): the `/health` probe ceiling and the bounded engine-log
    # tail were module constants in `app/latex/compile.py`; both are Settings
    # fields now (PLAT-04). Kept at the same defaults so behaviour is unchanged.
    "latex_probe_timeout_seconds",
    "latex_log_tail_chars",
    # Phase 5 (RANK-08 / D-91): the two ranking spend ceilings and D-94's operator
    # off switch. The numeric pair is also covered by LIMIT_FIELDS; the switch is
    # guarded by the surface tier only (see LIMIT_FIELDS).
    "ranking_max_calls_per_run",
    "ranking_max_calls_per_day",
    "ranking_enabled",
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
    # Phase 4: the compile ceiling (60, above DISTINCTIVE_THRESHOLD_FLOOR, so it
    # genuinely contributes to the literal scan) and the importer line cap.
    #
    # ASYMMETRY, deliberately: `tex_import_max_depth` is a required Settings field
    # but is NOT listed here. Its small structural default (12) would collide with
    # ordinary integer literals in the parser and make the absence scan noisy
    # rather than discriminating — the ceiling is still configuration, it is just
    # not what the literal scan exists to catch.
    "tectonic_timeout_seconds",
    "tex_import_max_lines",
    # Phase 4 (WR-03): the bounded engine-log tail (4000, above
    # DISTINCTIVE_THRESHOLD_FLOOR, so it genuinely contributes to the scan).
    "latex_log_tail_chars",
    # Phase 5 (RANK-08 / D-91): both ranking spend ceilings. Distinctive integers
    # above the floor, so listing them here is what makes the absence scan cover
    # them. `ranking_enabled` is deliberately absent — it is a boolean, and
    # `test_every_limit_field_is_a_required_numeric_ceiling` requires a numeric
    # default for every field in this tuple.
    "ranking_max_calls_per_run",
    "ranking_max_calls_per_day",
)

#: The Phase-4 ceilings (PLAT-04 applied to the LaTeX lane), listed explicitly so a
#: future edit that drops one from either guard below fails loudly rather than
#: silently un-covering it.
PHASE_FOUR_CEILINGS = (
    "tectonic_timeout_seconds",
    "tex_import_max_lines",
    "tex_import_max_depth",
    # WR-03: the `/health` probe ceiling and the engine-log tail bound. The
    # probe timeout is a FLOAT, so it is guarded at the surface tier only.
    "latex_probe_timeout_seconds",
    "latex_log_tail_chars",
)

#: The Phase-4 ceilings that are DISTINCTIVE integers (the literal scan's set).
PHASE_FOUR_DISTINCTIVE_CEILINGS = (
    "tectonic_timeout_seconds",
    "tex_import_max_lines",
    # WR-03: the bounded engine-log tail (4000) joins the scan; the probe
    # timeout is a float and is therefore not scannable (see LIMIT_FIELDS).
    "latex_log_tail_chars",
)

#: The Phase-5 ceilings (RANK-08 / PLAT-04 applied to ranking spend). Both are
#: integers and both are ceilings an operator may need to tune, so both appear in
#: both the surface guard and LIMIT_FIELDS. `ranking_enabled` is deliberately NOT
#: one of them: it is a switch, not a ceiling.
PHASE_FIVE_CEILINGS = (
    "ranking_max_calls_per_run",
    "ranking_max_calls_per_day",
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

#: Directories the absence check scans. `app/probe` arrives in plan 01-06;
#: `app/latex` and `app/cv` arrive in plan 04-02/04-03 (PLAT-04 widened to the
#: LaTeX lane, so a hard-coded engine ceiling there is caught too).
SCANNED_DIRS = ("app/probe", "app/pipeline", "app/latex", "app/cv")


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


def test_the_phase_four_ceilings_are_guarded() -> None:
    """Every Phase-4 ceiling must be asserted by the surface guard (PLAT-04)."""
    for field in PHASE_FOUR_CEILINGS:
        assert field in REQUIRED_SETTINGS_FIELDS, (
            f"{field} is a Phase-4 ceiling but REQUIRED_SETTINGS_FIELDS omits it"
        )
    for field in PHASE_FOUR_DISTINCTIVE_CEILINGS:
        assert field in LIMIT_FIELDS, (
            f"{field} is a distinctive numeric ceiling but LIMIT_FIELDS does not "
            "cover it"
        )
    # The written-down asymmetry: a small structural default stays a Settings field
    # without joining the literal scan, so the scan stays discriminating.
    assert "tex_import_max_depth" not in LIMIT_FIELDS, (
        "tex_import_max_depth joined LIMIT_FIELDS — its small default would make "
        "the absence scan noisy; either justify the change or leave the scan alone"
    )


def test_the_phase_five_ceilings_are_guarded() -> None:
    """Every Phase-5 ceiling must be asserted by BOTH guards (PLAT-04 / RANK-08)."""
    for field in PHASE_FIVE_CEILINGS:
        assert field in REQUIRED_SETTINGS_FIELDS, (
            f"{field} is a Phase-5 ceiling but REQUIRED_SETTINGS_FIELDS omits it"
        )
        assert field in LIMIT_FIELDS, (
            f"{field} is a distinctive numeric ceiling but LIMIT_FIELDS does not "
            "cover it"
        )
    # The written-down asymmetry: D-94's off switch is not a ceiling, so it must
    # stay out of LIMIT_FIELDS (which requires a numeric default).
    assert "ranking_enabled" not in LIMIT_FIELDS, (
        "ranking_enabled joined LIMIT_FIELDS — its boolean default would fail "
        "test_every_limit_field_is_a_required_numeric_ceiling"
    )


def test_the_phase_five_ceilings_are_environment_tunable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A config field no test can override is only half a config field."""
    assert Settings.model_fields["ranking_max_calls_per_run"].default == 40
    assert Settings.model_fields["ranking_max_calls_per_day"].default == 400

    monkeypatch.setenv("RANKING_MAX_CALLS_PER_RUN", "7")
    monkeypatch.setenv("RANKING_MAX_CALLS_PER_DAY", "70")

    refreshed = Settings()

    assert refreshed.ranking_max_calls_per_run == 7
    assert refreshed.ranking_max_calls_per_day == 70


def test_ranking_enabled_is_environment_tunable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-94's off switch is configuration, not a code change or a call-site edit."""
    assert Settings.model_fields["ranking_enabled"].default is True

    monkeypatch.setenv("RANKING_ENABLED", "false")

    assert Settings().ranking_enabled is False


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


def test_the_phase_four_ceilings_are_environment_tunable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WR-03: a config field no test can override is only half a config field."""
    assert Settings.model_fields["latex_probe_timeout_seconds"].default == 5.0
    assert Settings.model_fields["latex_log_tail_chars"].default == 4000

    monkeypatch.setenv("LATEX_PROBE_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("LATEX_LOG_TAIL_CHARS", "512")

    refreshed = Settings()

    assert refreshed.latex_probe_timeout_seconds == 2.5
    assert refreshed.latex_log_tail_chars == 512


def test_the_engine_log_tail_bound_comes_from_settings_at_call_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WR-03: a patched setting must change what `compile.py` DOES.

    Asserting the field exists is not enough — the module used to own a private
    `_LOG_TAIL_CHARS` constant that no setting could influence.
    """
    from app.latex import compile as compile_module

    monkeypatch.setattr(settings, "latex_log_tail_chars", 10)

    assert compile_module._tail("0123456789ABCDEF") == "6789ABCDEF"


async def test_the_probe_timeout_comes_from_settings_at_call_time(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """WR-03: a slow engine must time out at the SETTING, not a hard-coded 5.0."""
    from app.latex import compile as compile_module

    slow = tmp_path / "slow-engine"
    slow.write_text("#!/bin/sh\nsleep 2\n", encoding="utf-8")
    slow.chmod(0o755)

    monkeypatch.setattr(settings, "latex_probe_timeout_seconds", 0.05)

    probe = await compile_module._probe(str(slow))

    assert probe.available is False
    assert probe.error == "timeout"


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
