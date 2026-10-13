"""The operator's live V2 contract lane — spec fetch + diff only (D-57).

**Never runs in the default lane**: `pyproject.toml` sets
`addopts = "-m 'not live'"`, so the default suite structurally cannot reach a live
server. This module is selected explicitly, and the interpreter MUST have the
project's native dependencies built for the platform you run it on — a musl
container venv cannot load on a glibc host (`ModuleNotFoundError: No module named
'pydantic_core._pydantic_core'`). Run it **in the container** with
`.venv/bin/python`, or **on the host** with `.venv-host/bin/python`:

    # in the container (musl venv):
    OPENCODE_BASE_URL=http://127.0.0.1:4096 \\
        .venv/bin/python -m pytest -q -m live tests/llm/test_contract_live.py

    # on the host (glibc venv built on the host):
    OPENCODE_BASE_URL=http://127.0.0.1:4096 \\
        .venv-host/bin/python -m pytest -q -m live tests/llm/test_contract_live.py

What it does: fetches the running V2 server's OpenAPI spec (`GET /openapi.json`,
HTTP basic auth required — the spec's own `security: []` is a lie, Pitfall P8),
projects it through the SAME fact shape `tests/llm/fixtures/opencode-doc.json`
records, and fails loudly naming every divergent pointer. It also reads
`GET /api/info` for the RUNNING server version and asserts the committed
`_meta.server_version` matches — an upgrade fails here (D-150).

The committed slice is a **projection** (D-149): it pins a fixed set of facts so
unrelated OpenAPI churn cannot fail the test. So a committed fact is honoured when
every one of its members is present in the live spec; a renamed or removed
spelling still fails, which is the drift D-150 exists to catch.

What it deliberately does NOT do: make a model call. No `POST` at all, and no path
under `/session` (D-57). The real call lives in the in-app selftest
(`POST /settings/llm-test`) and in `tests/llm/test_live_structured_call.py`.

A drift is fixed by refreshing the fixture **deliberately**, per
`docs/runbook-opencode-contract.md` — never by editing the slice to match a guess.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config import settings
from app.llm import contract

pytestmark = pytest.mark.live

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "opencode-doc.json"


def _basic_auth_if_password_set() -> httpx.BasicAuth | None:
    """The same auth rule as `OpenCodeServerBackend._auth()` (D-07).

    BasicAuth only when a password is configured; an empty password means "send
    no auth header", not "send blanks".
    """
    password = settings.opencode_server_password
    if not password:
        return None
    return httpx.BasicAuth("opencode", password)


# --- projection helpers (test-local by design: never move these into app/) ----


def _name_set(value: Any) -> set[str]:
    """Property NAMES from an OpenAPI `properties` object, or the values of a list."""
    if isinstance(value, dict):
        return {str(key) for key in value}
    if isinstance(value, (list, tuple)):
        return {str(item) for item in value}
    return set()


def _ref(node: Any) -> str | None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        return ref if isinstance(ref, str) else None
    return None


def _prop(schema: Any, name: str) -> Any:
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    value = properties.get(name)
    return value if isinstance(value, dict) else {}


def _resolve(schemas: dict[str, Any], node: Any) -> dict[str, Any]:
    """Follow `$ref` chains into `components.schemas` until a concrete node.

    The live spec expresses some nodes indirectly: a response schema may be a
    `$ref` to a named component (or a leaf with an `enum`). Reading `.get("required")`
    off the *ref* node yields `None` — a false drift that fails the guard. Resolving
    keeps the guard's teeth: a renamed or removed target resolves to `{}` (a drift
    fires), while a resolved target's changed value still differs. Already-seen refs
    are tracked so a cyclic `$ref` cannot loop forever.
    """
    seen: set[str] = set()
    current: Any = node
    while isinstance(current, dict):
        ref = _ref(current)
        if not ref or ref in seen:
            break
        seen.add(ref)
        target = schemas.get(ref.rsplit("/", 1)[-1])
        if not isinstance(target, dict):
            return {}
        current = target
    return current if isinstance(current, dict) else {}


def _json_content(node: Any) -> dict[str, Any]:
    """The `application/json` schema of an OpenAPI requestBody/response object."""
    if not isinstance(node, dict):
        return {}
    content = node.get("content")
    if not isinstance(content, dict):
        return {}
    media = content.get("application/json")
    if not isinstance(media, dict):
        return {}
    schema = media.get("schema")
    return schema if isinstance(schema, dict) else {}


def _path_post(spec: dict[str, Any], path: str) -> dict[str, Any]:
    """`paths[path].post`, or `{}` — total, so a renamed path reports drift."""
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return {}
    node = paths.get(path)
    if not isinstance(node, dict):
        return {}
    post = node.get("post")
    return post if isinstance(post, dict) else {}


def _response_200(node: Any) -> dict[str, Any]:
    """The `200` response object of an OpenAPI operation, or `{}`."""
    if not isinstance(node, dict):
        return {}
    responses = node.get("responses")
    if not isinstance(responses, dict):
        return {}
    response = responses.get("200")
    return response if isinstance(response, dict) else {}


# --- the V2 fact projection ----------------------------------------------------


def _live_facts(spec: dict[str, Any]) -> dict[str, Any]:
    """Project the live V2 spec into the fact keys the committed slice records."""
    components = spec.get("components")
    schemas = components.get("schemas") if isinstance(components, dict) else None
    schemas = schemas if isinstance(schemas, dict) else {}

    session_post = _path_post(spec, contract.V2_SESSION_PATH)
    generate_post = _path_post(spec, contract.GENERATE_DOC_PATH)
    generate_body = _json_content(generate_post.get("requestBody"))
    # The generate response schema is a `$ref` into components; resolve it so a
    # renamed target reports drift rather than resolving to `{}` silently.
    generate_response = _resolve(
        schemas, _json_content(_response_200(generate_post))
    )
    model_ref = schemas.get("Model.Ref")
    model_ref = model_ref if isinstance(model_ref, dict) else {}

    return {
        "session_request_properties": _name_set(
            _json_content(session_post.get("requestBody")).get("properties")
        ),
        "generate_request_properties": _name_set(generate_body.get("properties")),
        "generate_request_required": _name_set(generate_body.get("required")),
        "model_ref_properties": _name_set(model_ref.get("properties")),
        "model_ref_required": _name_set(model_ref.get("required")),
        "generate_response_required": _name_set(generate_response.get("required")),
    }


def _committed_facts(fixture: dict[str, Any]) -> dict[str, Any]:
    """The same fact keys, read from the committed slice."""
    components = fixture.get("components")
    schemas = components.get("schemas") if isinstance(components, dict) else None
    schemas = schemas if isinstance(schemas, dict) else {}

    session_post = _path_post(fixture, contract.V2_SESSION_PATH)
    generate_post = _path_post(fixture, contract.GENERATE_DOC_PATH)
    model_ref = schemas.get("Model.Ref")
    model_ref = model_ref if isinstance(model_ref, dict) else {}
    generate_response = schemas.get("SessionGenerateResponse")
    generate_response = generate_response if isinstance(generate_response, dict) else {}

    return {
        "session_request_properties": _name_set(
            session_post.get("request_body_properties")
        ),
        "generate_request_properties": _name_set(
            generate_post.get("request_body_properties")
        ),
        "generate_request_required": _name_set(
            generate_post.get("request_body_required")
        ),
        "model_ref_properties": _name_set(model_ref.get("properties")),
        "model_ref_required": _name_set(model_ref.get("required")),
        "generate_response_required": _name_set(generate_response.get("required")),
    }


def _diff_facts(committed: dict[str, Any], live: dict[str, Any]) -> list[str]:
    """Every pointer whose committed fact the live spec no longer honours.

    Every fact here is a set of wire names, and the committed slice is a
    projection (see the module docstring): a fact is honoured when each committed
    member is present in the live set. An extra live property (unrelated churn)
    does not fail it; a renamed or removed member — the drift that matters — does.
    """
    diverged: list[str] = []
    for pointer in sorted(committed):
        want = committed[pointer]
        got = live.get(pointer)
        have = got if isinstance(got, set) else set()
        missing = want - have
        if missing:
            diverged.append(
                f"{pointer}: committed={sorted(want)!r} live={sorted(have)!r} "
                f"missing={sorted(missing)!r}"
            )
    return diverged


# --- the operator lane ---------------------------------------------------------


async def test_live_spec_matches_the_committed_slice() -> None:
    """One `GET /openapi.json` + one `GET /api/info`; no model call (D-57)."""
    assert FIXTURE_PATH.exists(), (
        f"missing {FIXTURE_PATH} — the committed slice is the diff's baseline"
    )
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    observed: list[tuple[str, str]] = []

    async def _record(request: httpx.Request) -> None:
        observed.append((request.method, request.url.path))

    async with httpx.AsyncClient(
        base_url=settings.opencode_base_url,
        timeout=settings.opencode_timeout_seconds,
        auth=_basic_auth_if_password_set(),
        event_hooks={"request": [_record]},
    ) as client:
        spec_response = await client.get(contract.OPENAPI_PATH)
        spec_response.raise_for_status()
        spec: dict[str, Any] = spec_response.json()
        # D-150: the RUNNING server version lives only on `/api/info`; `/openapi.json`
        # carries a static spec version, not the server's.
        info: dict[str, Any] = (await client.get(contract.INFO_PATH)).json()

    # D-57 / T-07.1-14: spec fetch + diff only. Structurally no POST can occur, and
    # nothing under `/session` (V1) or `/api/session` (V2) is ever touched.
    assert observed, "no request was recorded — the no-call guard would be vacuous"
    assert {method for method, _ in observed} == {"GET"}
    assert all(not path.startswith("/session") for _, path in observed)
    assert all("/session" not in path for _, path in observed)

    diffs = _diff_facts(_committed_facts(fixture), _live_facts(spec))
    assert diffs == [], (
        "opencode /openapi.json no longer honours the committed V2 slice. Confirm "
        "the drift is real (read each pointer above), then refresh "
        "tests/llm/fixtures/opencode-doc.json DELIBERATELY via "
        f"docs/runbook-opencode-contract.md. Divergent pointers: {diffs}"
    )

    observed_version = info.get(contract.SERVER_INFO_VERSION_FIELD)
    committed_version = fixture["_meta"]["server_version"]
    assert observed_version == committed_version, (
        "the running server version changed: refresh the fixture deliberately and "
        f"record the observed GET /api/info version ({observed_version!r}) in "
        f"_meta.server_version (currently {committed_version!r}); see "
        "docs/runbook-opencode-contract.md"
    )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-m", "live"])
