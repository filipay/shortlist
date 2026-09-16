"""T-02-04 / T-02-SC — the one new dependency is pinned and bound to what is installed.

`rapidfuzz` is Phase 2's only new runtime dependency. Its package-legitimacy gate
returned `SUS` (`too-new`, `unknown-downloads`), so the exact pin was cleared by a
blocking human checkpoint **before** the install ran. These tests keep the
declaration and the installed distribution from drifting apart afterwards: a
silent `pip install`, an unpinned range, or a `requirements.txt` that falls out of
step with `pyproject.toml` all fail here.

`tomllib` is stdlib on 3.11+, and the project pins >=3.13, so this adds no
dependency of its own (which would be self-defeating for a dependency guard).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PACKAGE = "rapidfuzz"
PIN = "rapidfuzz==3.14.6"
PINNED_VERSION = "3.14.6"


def _pyproject_dependencies() -> list[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return list(data["project"]["dependencies"])


def _requirements_entries() -> list[str]:
    """Non-blank, non-comment lines of requirements.txt."""
    return [
        stripped
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if (stripped := line.strip()) and not stripped.startswith("#")
    ]


def test_rapidfuzz_pin_is_declared_exactly() -> None:
    dependencies = _pyproject_dependencies()
    assert PIN in dependencies, f"{PIN} is missing from [project].dependencies"

    requirements = _requirements_entries()
    assert PIN in requirements, f"{PIN} is missing from requirements.txt"

    # No entry naming the package without an exact pin — a floating range or a
    # bare name is exactly the drift this guard exists to catch.
    for entry in (*dependencies, *requirements):
        if entry.startswith(PACKAGE):
            assert "==" in entry, f"unpinned {PACKAGE} entry: {entry!r}"


def test_rapidfuzz_imports_at_the_pinned_version() -> None:
    import rapidfuzz

    assert rapidfuzz.__version__ == PINNED_VERSION
    assert callable(rapidfuzz.fuzz.token_sort_ratio)
    assert callable(rapidfuzz.fuzz.token_set_ratio)

    # Executable evidence for the hazard plan 02-04 must design around: token-set
    # ratio returns 100.0 when one string is a subset of the other, so
    # "Senior Software Engineer" vs "Software Engineer" would score a perfect 100.
    # That is why 02-04 gates on token_sort_ratio and treats token_set_ratio as a
    # diagnostic only (RESEARCH Summary finding 3 / PITFALLS P3).
    assert (
        rapidfuzz.fuzz.token_set_ratio(
            "fuzzy was a bear but not a dog", "fuzzy was a bear"
        )
        == 100.0
    )
