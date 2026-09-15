"""D-24 / T-01-22 — `app.domain` is pure: no I/O import is reachable from it.

The guard is an AST walk, not a regex over file text, so a commented-out import
or a string containing `sqlalchemy` cannot create a false pass or a false fail.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

FORBIDDEN_TOP_LEVEL_MODULES = frozenset(
    {"httpx", "sqlalchemy", "jobspy", "jinja2", "subprocess", "fastapi"}
)

DOMAIN_DIR = Path(__file__).resolve().parents[1] / "app" / "domain"


def _imported_top_level_modules(source: str, *, filename: str = "<test>") -> set[str]:
    """Top-level module names imported by `source`, via `ast.walk`."""
    tree = ast.parse(source, filename=filename)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # a relative import inside the package
                continue
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def test_the_walker_actually_detects_a_forbidden_import() -> None:
    """A guard that cannot fail is not a guard."""
    offenders = _imported_top_level_modules(
        "import httpx\nfrom sqlalchemy import select\n"
    )

    assert offenders & FORBIDDEN_TOP_LEVEL_MODULES == {"httpx", "sqlalchemy"}


def test_the_walker_ignores_relative_and_harmless_imports() -> None:
    offenders = _imported_top_level_modules(
        "from __future__ import annotations\n"
        "import hashlib\n"
        "from .models import User\n"
    )

    assert offenders & FORBIDDEN_TOP_LEVEL_MODULES == set()


def test_domain_package_has_modules() -> None:
    modules = sorted(path.name for path in DOMAIN_DIR.glob("*.py"))

    assert "listing.py" in modules
    assert "models.py" in modules
    assert "sanitize.py" in modules


def test_domain_imports_no_io() -> None:
    offenders: dict[str, list[str]] = {}
    scanned = 0

    for path in sorted(DOMAIN_DIR.rglob("*.py")):
        scanned += 1
        bad = sorted(
            _imported_top_level_modules(
                path.read_text(encoding="utf-8"), filename=str(path)
            )
            & FORBIDDEN_TOP_LEVEL_MODULES
        )
        if bad:
            offenders[str(path.relative_to(DOMAIN_DIR.parents[1]))] = bad

    assert scanned > 0, "no modules were scanned — the guard is vacuous"
    assert offenders == {}, (
        f"app.domain imports I/O — move it behind a port: {offenders}"
    )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
