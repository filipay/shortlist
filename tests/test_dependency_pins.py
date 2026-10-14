"""T-02-04 / T-04-SC — new dependencies are pinned and bound to what is installed.

Each package here is a new runtime dependency whose package-legitimacy gate
returned `SUS` (`too-new`, `unknown-downloads`), so the exact pin was cleared by a
blocking human checkpoint **before** the install or the manifest edit ran. These
tests keep the declaration and the installed distribution from drifting apart
afterwards: a silent `pip install`, an unpinned range, or a `requirements.txt`
that falls out of step with `pyproject.toml` all fail here.

`rapidfuzz` is Phase 2's dependency (T-02-04). `pypdf` and `pyyaml` are Phase 4's
(T-04-SC): `pyyaml` is a dev→runtime promotion of an already-installed pin.
`apscheduler` is Phase 8's (T-08-01).

`tomllib` is stdlib on 3.11+, and the project pins >=3.13, so this adds no
dependency of its own (which would be self-defeating for a dependency guard).
"""

from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PACKAGE = "rapidfuzz"
PIN = "rapidfuzz==3.14.6"
PINNED_VERSION = "3.14.6"

# (distribution name, exact pin string, installed version). The pin string must
# appear verbatim in BOTH manifests (D-17); the version must match the installed
# distribution. Table-driven so a third package costs one row, not a third test.
PINNED_PACKAGES = (
    ("pypdf", "pypdf==6.19.0", "6.19.0"),
    ("pyyaml", "pyyaml==6.0.3", "6.0.3"),
    # Phase 8's scheduler (T-08-01); the pin string must appear in BOTH manifests.
    ("apscheduler", "apscheduler==3.11.3", "3.11.3"),
)


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


def _declaration_misses(
    package: str, pin: str, dependencies: list[str], requirements: list[str]
) -> list[str]:
    """Return the ways `pin` is not declared exactly; empty list == guard satisfied.

    Split out so `test_the_pin_checker_can_actually_fail` can prove the check
    discriminates instead of passing on empty input (mirrors
    `tests/test_config.py::test_the_literal_scan_can_actually_fail`).
    """
    misses: list[str] = []
    if pin not in dependencies:
        misses.append(f"{pin} is missing from [project].dependencies")
    if pin not in requirements:
        misses.append(f"{pin} is missing from requirements.txt")
    # No entry naming the package without an exact pin — a floating range or a
    # bare name is exactly the drift this guard exists to catch.
    for entry in (*dependencies, *requirements):
        if entry.startswith(package) and "==" not in entry:
            misses.append(f"unpinned {package} entry: {entry!r}")
    return misses


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


def test_pinned_package_is_declared_exactly() -> None:
    dependencies = _pyproject_dependencies()
    requirements = _requirements_entries()

    for package, pin, _ in PINNED_PACKAGES:
        misses = _declaration_misses(package, pin, dependencies, requirements)
        assert misses == [], "; ".join(misses)


def test_pinned_package_imports_at_the_pinned_version() -> None:
    for package, _, version in PINNED_PACKAGES:
        assert importlib.metadata.version(package) == version, (
            f"{package} is installed at {importlib.metadata.version(package)}, "
            f"not the pinned {version}"
        )


def test_the_latex_marker_is_registered_and_excluded() -> None:
    """A registered-but-not-excluded marker fails every machine with no engine;
    an exclusion with no registered marker warns on every run. Assert both halves
    here so neither can drift alone (D-69 / T-04-04)."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    ini_options = data["tool"]["pytest"]["ini_options"]

    markers = ini_options["markers"]
    assert any(marker.startswith("latex:") for marker in markers), markers
    assert "not latex" in ini_options["addopts"], ini_options["addopts"]


def test_the_pin_checker_can_actually_fail() -> None:
    """A guard that cannot fail is not a guard."""
    dependencies = _pyproject_dependencies()
    requirements = _requirements_entries()

    # An unpinned range for a pinned package must be reported.
    unpinned = _declaration_misses(
        "pypdf", "pypdf==6.19.0", dependencies, [*requirements, "pypdf>=6"]
    )
    assert unpinned == ["unpinned pypdf entry: 'pypdf>=6'"], unpinned

    # A manifest that stops mirroring the other must be reported.
    missing = _declaration_misses(
        "pyyaml",
        "pyyaml==6.0.3",
        [dep for dep in dependencies if not dep.startswith("pyyaml")],
        requirements,
    )
    assert missing == ["pyyaml==6.0.3 is missing from [project].dependencies"], missing
