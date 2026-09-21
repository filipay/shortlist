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
APP_DIR = PROJECT_ROOT / "app"
LLM_CALL_PATH_DIRS = ("app/pipeline", "app/api", "app/web", "app/domain", "app/probe")
#: Excluded from the httpx scan on purpose — the board transports. Asserted below
#: to actually import httpx, so the exclusion cannot become an empty courtesy.
EXCLUDED_HTTPX_DIRS = ("app/sources",)
#: The DECLARED process hosts. `subprocess` is confined to these and nothing else.
#: `app/llm` spawns the opencode CLI fallback; `app/latex` spawns the compile
#: engine. `app/latex` is a second process host BY DESIGN (D-76) — the compile
#: port — and the two port boundaries must not merge: moving the compile call into
#: `app/llm/` to satisfy the letter of a single-host rule would collapse them.
#: Asserted below to actually import `subprocess`, so the carve-out is not an empty
#: courtesy.
SUBPROCESS_EXEMPT_DIRS = ("app/llm", "app/latex")
SUBPROCESS_EXEMPT_ROOTS = tuple(
    PROJECT_ROOT / relative for relative in SUBPROCESS_EXEMPT_DIRS
)


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


def test_subprocess_is_confined_to_declared_process_hosts() -> None:
    offenders: dict[str, list[str]] = {}
    scanned = 0

    for path in _python_modules(APP_DIR):
        if any(root in path.parents for root in SUBPROCESS_EXEMPT_ROOTS):
            continue
        scanned += 1
        if _imports_of(path, "subprocess"):
            offenders[str(path.relative_to(PROJECT_ROOT))] = ["subprocess"]

    assert scanned > 0, "no modules were scanned — the guard is vacuous"
    assert offenders == {}, (
        "a process spawn outside a declared process host is an RCE path outside "
        f"a port: {offenders}"
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


def test_the_latex_exclusion_is_deliberate_not_accidental() -> None:
    """`app/latex` genuinely imports `subprocess` and is genuinely outside the scan.

    Copied in shape from `test_the_sources_exclusion_is_deliberate_not_accidental`:
    the carve-out must not become an empty courtesy, and none of the declared
    process hosts may sit inside a directory the global guard still scans.
    """
    exempt_roots = [PROJECT_ROOT / relative for relative in SUBPROCESS_EXEMPT_DIRS]

    hosts = [path for root in exempt_roots for path in _python_modules(root)]
    assert hosts, "no declared process host modules exist — the rationale is stale"

    # Every declared host is genuinely excluded by the guard's skip predicate.
    for path in hosts:
        assert any(root in path.parents for root in SUBPROCESS_EXEMPT_ROOTS), (
            f"{path} is not covered by SUBPROCESS_EXEMPT_ROOTS"
        )

    flagged = sum(1 for path in hosts if _imports_of(path, "subprocess"))
    assert flagged > 0, (
        "no declared process host imports subprocess — the exclusion no longer "
        "has a reason"
    )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
