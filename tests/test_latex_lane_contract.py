"""D-69 — the `latex` lane is collected-and-skipped, never silently deselected.

The distinction is the phase's honesty control: a deselected lane hides the fact
that the gate was never run, while a collected-and-skipped lane reports it. The
marker registration and its `addopts` exclusion are guarded in
`tests/test_dependency_pins.py`; this file guards the observable consequence —
an explicit `-m latex` selection still collects the nodes the hermetic default
lane excludes.

The nodes are collected but not run (they are `skipif` on a missing engine), so
this remains a hermetic test that needs no Docker and no Tectonic.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _collect(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ}
    env.pop("PYTEST_ADDOPTS", None)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--collect-only",
            "-p",
            "no:cacheprovider",
            *args,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def test_the_default_lane_deselects_the_latex_nodes() -> None:
    result = _collect("tests/latex")

    # Exit 5 is pytest's "no tests collected" — everything in the lane was
    # deselected by the default addopts, which is exactly the documented shape.
    assert result.returncode in (0, 5), result.stderr
    assert "deselected" in result.stdout
    assert "tests/latex/test_compile.py::" not in result.stdout


def test_an_explicit_latex_selection_collects_them_instead() -> None:
    result = _collect("-m", "latex", "tests/latex")

    assert result.returncode == 0, result.stderr
    assert "tests/latex/test_compile.py::" in result.stdout
    assert "tests/latex/test_fact_equivalence.py::" in result.stdout


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
