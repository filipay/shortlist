"""04-05-03 — the committed verdict, runbook and README keep their promised shape.

Plan 04-05 Task 3 verified these with one-off shell assertions. They are the
phase's disclosure and repudiation controls (T-04-28/T-04-29), so they belong in
the sampled suite: a later edit to a committed document must not silently drop a
control or start claiming more than was measured.

The `.planning/STATE.md` pointer the plan also asserts is deliberately not pinned
here: STATE.md is orchestrator-owned mutable planning state, and a future phase
rewriting it would produce a false failure in a permanent gate. It was verified at
execution time and is recorded in the SUMMARY.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERDICT = PROJECT_ROOT / "docs" / "probes" / "2026-09-21-cv-tex-spike.md"
RUNBOOK = PROJECT_ROOT / "docs" / "runbook-latex-compile.md"
README = PROJECT_ROOT / "docs" / "probes" / "README.md"
LANE_FILES = (
    PROJECT_ROOT / "tests" / "latex" / "test_compile.py",
    PROJECT_ROOT / "tests" / "latex" / "test_fact_equivalence.py",
)
GATE_COMMAND = "docker compose run --rm app pytest -m latex"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(r"\b(?:phone|tel|mobile|fax)\b|\+353", re.IGNORECASE)


def _verdict() -> str:
    assert VERDICT.exists(), VERDICT
    return VERDICT.read_text(encoding="utf-8")


def test_the_verdict_carries_exactly_one_status_marker_and_it_is_partial() -> None:
    """Two markers is how a document ends up claiming two states at once."""
    markers = re.findall(r"^\*\*Status:\*\*\s*(.*)$", _verdict(), re.MULTILINE)

    assert len(markers) == 1, markers
    assert markers[0].strip() == "PARTIAL", markers


def test_the_verdict_names_the_real_document_path_and_the_trigger_command() -> None:
    text = _verdict()

    assert "UNRESOLVED" in text
    assert "cv/base.tex" in text
    assert "bash scripts/cv-tex-spike.sh" in text


def _assert_substantial(text: str) -> None:
    """An absence check over an empty or gutted document must not pass."""
    assert len(text) > 1000, len(text)
    assert "PARTIAL" in text


def test_the_verdict_carries_no_email_or_phone_shaped_string() -> None:
    text = _verdict()
    _assert_substantial(text)

    assert EMAIL_RE.findall(text) == []
    assert PHONE_RE.search(text) is None


def test_the_verdict_carries_no_fixture_content() -> None:
    """Committed documents carry counts and names, never CV content."""
    text = _verdict()
    _assert_substantial(text)

    for leaked in ("Northwind", "Senior Engineer", "example.invalid"):
        assert leaked not in text


def test_the_fallback_is_either_measured_with_units_or_declared_unmeasured() -> None:
    text = _verdict()

    assert "D-76" in text
    declared_unmeasured = (
        re.search(r"not (yet )?taken", text, re.IGNORECASE) is not None
    )
    measured = (
        "Dockerfile.texlive" in text and re.search(r"\d+\s*MB", text) is not None
    )

    assert declared_unmeasured or measured


def test_the_runbook_names_the_gate_the_engine_switch_and_the_first_run_step() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    assert GATE_COMMAND in text
    assert "Dockerfile.texlive" in text
    assert "LATEX_ENGINE=texlive" in text
    assert "mkdir -p cv artifacts" in text


def test_the_gate_command_is_the_same_string_the_lane_tests_skip_on() -> None:
    """One documented gate command, shared by the runbook and the lane skips."""
    for lane_file in LANE_FILES:
        assert GATE_COMMAND in lane_file.read_text(encoding="utf-8"), lane_file


def test_the_probes_readme_points_at_the_latex_probe_and_the_compile_runbook() -> None:
    text = README.read_text(encoding="utf-8")

    assert "cv-tex-spike" in text
    assert "runbook-latex-compile" in text


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
