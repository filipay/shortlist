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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOMAIN_DIR = PROJECT_ROOT / "app" / "domain"


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


# --- the LLM call path (T-3-18 / ARCHITECTURE §6.5) ---------------------------
#
# §6.5: "nothing outside `llm/` may import `httpx` or `subprocess`". The httpx half
# is scoped deliberately: `app/sources/linkedin.py` and `app/sources/indeed.py`
# legitimately `import httpx` for the public-page probe and never call the LLM, so a
# blanket all-of-`app/` rule would fail on day one and teach nothing (Pitfall P6).
# `subprocess` has no legitimate user outside `app/llm` today, so that half is global.
APP_DIR = PROJECT_ROOT / "app"
LLM_DIR = APP_DIR / "llm"
LLM_CALL_PATH_DIRS = ("app/pipeline", "app/api", "app/web", "app/domain", "app/probe")
#: Excluded from the httpx scan on purpose — the board transports. Asserted below
#: to actually import httpx, so the exclusion cannot become an empty courtesy.
EXCLUDED_HTTPX_DIRS = ("app/sources",)


def _python_modules(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return [
        path
        for path in sorted(directory.rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def _imports_of(path: Path, module: str) -> bool:
    return module in _imported_top_level_modules(
        path.read_text(encoding="utf-8"), filename=str(path)
    )


def test_the_llm_call_path_imports_no_httpx() -> None:
    offenders: dict[str, list[str]] = {}
    scanned = 0

    for relative in LLM_CALL_PATH_DIRS:
        for path in _python_modules(PROJECT_ROOT / relative):
            scanned += 1
            if _imports_of(path, "httpx"):
                offenders[str(path.relative_to(PROJECT_ROOT))] = ["httpx"]

    assert scanned > 0, "no modules were scanned — the guard is vacuous"
    assert offenders == {}, (
        "the LLM call path imports httpx outside app/llm — a second HTTP path "
        f"bypasses the port's controls: {offenders}"
    )


def test_no_module_outside_app_llm_imports_subprocess() -> None:
    offenders: dict[str, list[str]] = {}
    scanned = 0

    for path in _python_modules(APP_DIR):
        if LLM_DIR in path.parents:
            continue
        scanned += 1
        if _imports_of(path, "subprocess"):
            offenders[str(path.relative_to(PROJECT_ROOT))] = ["subprocess"]

    assert scanned > 0, "no modules were scanned — the guard is vacuous"
    assert offenders == {}, (
        f"a process spawn outside app/llm is an RCE path outside the port: {offenders}"
    )


def test_the_scoped_httpx_guard_can_actually_fail() -> None:
    """A guard that cannot fail is not a guard."""
    offenders = _imported_top_level_modules("import httpx\n") & {"httpx"}

    assert offenders == {"httpx"}


def test_the_sources_exclusion_is_deliberate_not_accidental() -> None:
    """`app/sources` genuinely imports httpx and is genuinely outside the scan."""
    excluded_roots = [PROJECT_ROOT / relative for relative in EXCLUDED_HTTPX_DIRS]
    scanned_roots = [PROJECT_ROOT / relative for relative in LLM_CALL_PATH_DIRS]

    transports = [
        path for root in excluded_roots for path in _python_modules(root)
    ]
    assert transports, "no excluded transport modules exist — the rationale is stale"

    flagged = 0
    for path in transports:
        if _imports_of(path, "httpx"):
            flagged += 1
        # None of them may sit inside a directory the scoped guard scans.
        assert not any(root in path.parents for root in scanned_roots), (
            f"{path} is inside a scanned directory but uses httpx"
        )

    assert flagged > 0, (
        "no excluded transport imports httpx — the exclusion no longer has a reason"
    )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
