"""SRC-06 / T-01-24 / PITFALLS P2 — no credentialed acquisition path under `app/`.

The bright line is architectural, not aspirational: no module under `app/` may read
a portal credential, build a cookie jar, or open an authenticated session — "at
any escalation level or behind any flag". The guard is an AST walk (so a
commented-out import or a docstring mentioning a token cannot create a false pass
or a false fail) plus a narrow raw-token scan. The pattern list lives here, in the
test, so SRC-06's assertion is reviewable by inspection.

The raw-token list is deliberately narrow. `app/config.py` legitimately declares
`opencode_server_password` — an env-supplied value for the LLM backend, which is a
different trust boundary from a job-portal login — so a bare `PASSWORD` token
would be a false positive. Planned plan 01-04's `tests/sources/test_indeed.py`
covers the adapter-shaped kwargs; this file broadens the same claim across all of
`app/` and adds the AST half.

The same carve-out applies at one point in the identifier matching: `auth` (below)
is evidence of a credential path in an *environment-variable name* or a
*string-literal argument*, but not as a bare keyword-argument name — `httpx`
takes a config-supplied credential as `auth=`, and that is exactly how
`app/llm/opencode_server.py` passes the optional local opencode password (D-07).
A portal credential still trips this guard through `username`, `password`,
`token`, `cookie`, `credentials` or a `login()`/`sign_in()` call.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"

#: Credential-shaped substrings, applied to collected *identifiers* — never to
#: arbitrary file text.
CREDENTIAL_PATTERNS: tuple[str, ...] = (
    "password",
    "passwd",
    "username",
    "user_name",
    "credential",
    "api_key",
    "apikey",
    "secret",
    "token",
    "cookie",
    "session_id",
    "login",
    "signin",
    "sign_in",
    "bearer",
    "auth",
    "email",
    "phone",
)

#: The same vocabulary minus `auth`, for *keyword-argument names*. See the module
#: docstring: `auth=` is how httpx takes a config-supplied credential and is not
#: evidence of a job-portal (SRC-06) path, while a `login()`/`sign_in()` call is
#: caught by `_authenticating_calls` and portal kwargs by the patterns below.
CREDENTIAL_KWARG_PATTERNS: tuple[str, ...] = tuple(
    pattern for pattern in CREDENTIAL_PATTERNS if pattern != "auth"
)

#: Callables whose keyword arguments are inspected: anything that could open a
#: session, carry a cookie, or establish an authenticated identity.
SESSION_CALLABLE_HINTS: tuple[str, ...] = (
    "session",
    "client",
    "cookie",
    "auth",
    "login",
    "signin",
)

#: Call names that establish an authenticated identity.
AUTHENTICATING_CALLS: frozenset[str] = frozenset(
    {"login", "log_in", "sign_in", "signin", "authenticate", "authorize"}
)

#: Raw tokens that must never appear as text anywhere under `app/`.
CREDENTIAL_TOKENS: tuple[str, ...] = (
    "JOBSPY_CREDS",
    "LINKEDIN_USERNAME",
    "LINKEDIN_PASSWORD",
    "INDEED_EMAIL",
    "INDEED_PASSWORD",
    "cookies=",
    "CookieJar",
    "http.cookiejar",
    "requests.Session",
)

EXPECTED_SCANNED_MODULE = "app/sources/indeed.py"


# --- collectors ---------------------------------------------------------------


def _app_sources() -> list[Path]:
    return [
        path
        for path in sorted(APP_DIR.rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def _dotted_name(node: ast.expr) -> str | None:
    """`os.environ.get` -> "os.environ.get"; any other node -> None."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        parts.reverse()
        return ".".join(parts)
    return None


def _literal_strings(nodes: Iterable[ast.expr]) -> list[str]:
    return [
        node.value
        for node in nodes
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def _environment_reads(tree: ast.AST) -> list[str]:
    """Every env-var name read via `os.getenv`, `os.environ[...]` or `.get`."""
    reads: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            dotted = _dotted_name(node.func) or ""
            if dotted in {"os.getenv", "getenv", "os.environ.get", "environ.get"}:
                reads.extend(_literal_strings(node.args))
                for keyword in node.keywords:
                    if keyword.arg in {"key", "name", "var", "env"}:
                        reads.extend(_literal_strings([keyword.value]))
        elif isinstance(node, ast.Subscript) and (
            _dotted_name(node.value) or ""
        ) in {"os.environ", "environ"}:
            reads.extend(_literal_strings([node.slice]))
    return reads


def _session_calls(tree: ast.AST) -> list[tuple[str, list[str], list[str]]]:
    """`(callable, kwarg-names, string-literal arguments)` for session-ish calls."""
    calls: list[tuple[str, list[str], list[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        dotted = _dotted_name(node.func)
        if dotted is None:
            continue
        leaf = dotted.split(".")[-1].casefold()
        if not any(hint in leaf for hint in SESSION_CALLABLE_HINTS):
            continue
        kwargs = [keyword.arg for keyword in node.keywords if keyword.arg]
        literals = _literal_strings(node.args) + _literal_strings(
            keyword.value for keyword in node.keywords
        )
        calls.append((dotted, kwargs, literals))
    return calls


def _authenticating_calls(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        dotted = _dotted_name(node.func)
        if dotted and dotted.split(".")[-1].casefold() in AUTHENTICATING_CALLS:
            names.append(dotted)
    return names


def _credential_matches(
    values: Iterable[str], patterns: tuple[str, ...] = CREDENTIAL_PATTERNS
) -> list[str]:
    return sorted(
        {value for value in values if any(p in value.casefold() for p in patterns)}
    )


# --- the guard ----------------------------------------------------------------


def test_the_scan_covers_the_application_package() -> None:
    scanned = [str(path.relative_to(APP_DIR.parents[0])) for path in _app_sources()]

    assert len(scanned) >= 10, f"too few modules scanned to be meaningful: {scanned}"
    assert EXPECTED_SCANNED_MODULE in scanned


def test_no_credential_read_or_authenticated_session_under_app() -> None:
    offenders: dict[str, list[str]] = {}

    for path in _app_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = str(path.relative_to(APP_DIR.parents[0]))
        found: list[str] = []

        found.extend(
            f"credential env read: {name}"
            for name in _credential_matches(_environment_reads(tree))
        )

        for dotted, kwargs, literals in _session_calls(tree):
            found.extend(
                f"{dotted}(... {name}=...)"
                for name in _credential_matches(kwargs, CREDENTIAL_KWARG_PATTERNS)
            )
            found.extend(
                f"{dotted}({value!r})" for value in _credential_matches(literals)
            )

        found.extend(
            f"authenticating call: {name}" for name in _authenticating_calls(tree)
        )

        if found:
            offenders[relative] = sorted(set(found))

    assert offenders == {}, (
        f"a credentialed acquisition path exists under app/: {offenders}"
    )


def test_no_credential_token_appears_as_text_under_app() -> None:
    offenders: dict[str, list[str]] = {}

    for path in _app_sources():
        text = path.read_text(encoding="utf-8").casefold()
        found = sorted({token for token in CREDENTIAL_TOKENS if token.casefold() in text})
        if found:
            offenders[str(path.relative_to(APP_DIR.parents[0]))] = found

    assert offenders == {}, f"a credential token reappeared under app/: {offenders}"


# --- non-vacuity: the collectors must be able to fail -------------------------


def test_the_walk_detects_a_credential_read() -> None:
    tree = ast.parse('import os\npw = os.getenv("LINKEDIN_PASSWORD")')

    assert _credential_matches(_environment_reads(tree)) == ["LINKEDIN_PASSWORD"]


def test_the_walk_detects_an_environ_subscript_read() -> None:
    tree = ast.parse('import os\nuser = os.environ["INDEED_EMAIL"]')

    assert _credential_matches(_environment_reads(tree)) == ["INDEED_EMAIL"]


def test_the_walk_detects_a_cookie_bearing_client() -> None:
    tree = ast.parse('httpx.AsyncClient(cookies={"session": "abc"})')

    kwargs = [name for _, names, _ in _session_calls(tree) for name in names]

    assert _credential_matches(kwargs) == ["cookies"]


def test_the_walk_detects_an_authenticating_call_and_its_kwargs() -> None:
    tree = ast.parse('client.login(username="a", password="b")')

    assert _authenticating_calls(tree) == ["client.login"]
    kwargs = [name for _, names, _ in _session_calls(tree) for name in names]
    assert _credential_matches(kwargs) == ["password", "username"]


def test_the_token_scan_detects_a_cookie_jar() -> None:
    source = "import http.cookiejar\njar = http.cookiejar.CookieJar()"

    found = sorted({token for token in CREDENTIAL_TOKENS if token.casefold() in source.casefold()})

    assert found == ["CookieJar", "http.cookiejar"]


def test_the_auth_kwarg_carve_out_is_narrow_and_deliberate() -> None:
    """`auth=` is not flagged; the same token still is everywhere else.

    `httpx.AsyncClient(auth=...)` is how the LLM backend takes its optional,
    config-supplied password (D-07). Portal-shaped kwargs and an `auth`-named
    environment read must still fail, so the carve-out cannot silently widen.
    """
    tree = ast.parse(
        'httpx.AsyncClient(auth=auth)\n'
        'client.login(username="u", password="p")\n'
        'os.getenv("LINKEDIN_AUTH")'
    )

    kwargs = [name for _, names, _ in _session_calls(tree) for name in names]
    assert _credential_matches(kwargs, CREDENTIAL_KWARG_PATTERNS) == [
        "password",
        "username",
    ]
    assert _credential_matches(kwargs) == ["auth", "password", "username"]
    assert _credential_matches(_environment_reads(tree)) == ["LINKEDIN_AUTH"]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
