"""The operator's live `/doc` contract lane — spec fetch + diff only (D-57).

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

What it does: fetches the running server's OpenAPI spec (`GET /doc`), projects it
through the SAME fact shape `tests/llm/fixtures/opencode-doc.json` records, and
fails loudly naming every divergent pointer. It also reads `GET /global/health`
and asserts the committed `_meta.server_version` matches — an upgrade fails here.

What it deliberately does NOT do: make a model call. No `POST /session`, no
`POST /session/{id}/message` (D-57). The real call lives in the in-app selftest
(`POST /settings/llm-test`, plan 03-01).

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
from app.llm.opencode_server import GLOBAL_HEALTH_PATH

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

    The live spec expresses some leaf schemas indirectly: `PermissionRule.action`
    is a `$ref` to `PermissionAction`, whose `enum` lives on the target. Reading
    `.get("enum")` off the *ref* node yields `None` and therefore an empty set — a
    false drift that fails the guard unconditionally. Resolving keeps the guard's
    teeth: a renamed or removed target resolves to `{}` (empty set -> drift fires),
    a changed enum still differs, and an inline enum passes through unchanged.
    Already-seen refs are tracked so a cyclic `$ref` cannot loop forever.
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


def _permission_rule_schema(
    schemas: dict[str, Any], session_body: dict[str, Any]
) -> dict[str, Any]:
    """The `PermissionRule` schema the session `permission` array points at.

    The live spec nests the deny rule behind the session body's `permission`
    property: an array whose `items` is a `$ref` into `components.schemas`. A
    wrapper schema (e.g. a `PermissionRuleset` that is itself an array) is
    followed one level. The literal `PermissionRule` name is the fallback, so a
    renamed rule still reports drift rather than resolving to `{}` silently.
    """
    items = _prop(session_body, "permission").get("items")
    ref = _ref(items if isinstance(items, dict) else {})
    if ref:
        resolved = schemas.get(ref.rsplit("/", 1)[-1])
        if isinstance(resolved, dict) and isinstance(resolved.get("properties"), dict):
            return resolved
        nested = _ref(resolved.get("items")) if isinstance(resolved, dict) else None
        if nested:
            candidate = schemas.get(nested.rsplit("/", 1)[-1])
            if isinstance(candidate, dict):
                return candidate
    fallback = schemas.get("PermissionRule")
    return fallback if isinstance(fallback, dict) else {}


def _live_facts(spec: dict[str, Any]) -> dict[str, Any]:
    """Project the live spec into the fact keys the committed slice records."""
    components = spec.get("components")
    schemas = components.get("schemas") if isinstance(components, dict) else None
    schemas = schemas if isinstance(schemas, dict) else {}

    session_post = _path_post(spec, contract.SESSION_PATH)
    message_post = _path_post(spec, contract.MESSAGE_DOC_PATH)
    message_body = _json_content(message_post.get("requestBody"))
    message_response = _json_content(
        (message_post.get("responses") or {}).get("200")
        if isinstance(message_post.get("responses"), dict)
        else {}
    )
    session_response = _json_content(
        (session_post.get("responses") or {}).get("200")
        if isinstance(session_post.get("responses"), dict)
        else {}
    )

    out_format = schemas.get("OutputFormatJsonSchema")
    out_format = out_format if isinstance(out_format, dict) else {}
    assistant = schemas.get("AssistantMessage")
    assistant = assistant if isinstance(assistant, dict) else {}
    error = schemas.get("StructuredOutputError")
    error = error if isinstance(error, dict) else {}
    error_data = _prop(error, "data")
    text_part = schemas.get("TextPartInput")
    text_part = text_part if isinstance(text_part, dict) else {}

    session_body = _json_content(session_post.get("requestBody"))
    permission_rule = _permission_rule_schema(schemas, session_body)
    return {
        "session_request_properties": _name_set(session_body.get("properties")),
        "session_response_200_ref": _ref(session_response),
        "message_operation_id": message_post.get("operationId"),
        "message_request_properties": _name_set(message_body.get("properties")),
        "message_request_required": _name_set(message_body.get("required")),
        "message_response_required": _name_set(message_response.get("required")),
        "message_info_ref": _ref(_prop(message_response, "info")),
        "output_format_properties": _name_set(out_format.get("properties")),
        "output_format_required": _name_set(out_format.get("required")),
        "output_format_type_enum": _name_set(
            _resolve(schemas, _prop(out_format, "type")).get("enum")
        ),
        "output_format_schema_ref": _ref(_prop(out_format, "schema")),
        "permission_rule_properties": _name_set(permission_rule.get("properties")),
        "permission_rule_required": _name_set(permission_rule.get("required")),
        "permission_action_enum": _name_set(
            _resolve(schemas, _prop(permission_rule, "action")).get("enum")
        ),
        "assistant_properties": _name_set(assistant.get("properties")),
        "assistant_required": _name_set(assistant.get("required")),
        "assistant_additional_properties": assistant.get("additionalProperties"),
        "structured_error_properties": _name_set(error.get("properties")),
        "structured_error_required": _name_set(error.get("required")),
        "structured_error_name_enum": _name_set(
            _resolve(schemas, _prop(error, "name")).get("enum")
        ),
        "structured_error_data_properties": _name_set(error_data.get("properties")),
        "structured_error_data_required": _name_set(error_data.get("required")),
        "text_part_properties": _name_set(text_part.get("properties")),
        "text_part_required": _name_set(text_part.get("required")),
        "text_part_type_enum": _name_set(_resolve(schemas, _prop(text_part, "type")).get("enum")),
    }


def _committed_facts(fixture: dict[str, Any]) -> dict[str, Any]:
    """The same fact keys, read from the committed slice."""
    components = fixture.get("components")
    schemas = components.get("schemas") if isinstance(components, dict) else None
    schemas = schemas if isinstance(schemas, dict) else {}

    session_post = _path_post(fixture, contract.SESSION_PATH)
    message_post = _path_post(fixture, contract.MESSAGE_DOC_PATH)
    refs = message_post.get("response_200_refs")
    refs = refs if isinstance(refs, dict) else {}

    out_format = schemas.get("OutputFormatJsonSchema")
    out_format = out_format if isinstance(out_format, dict) else {}
    permission_rule = schemas.get("PermissionRule")
    permission_rule = permission_rule if isinstance(permission_rule, dict) else {}
    assistant = schemas.get("AssistantMessage")
    assistant = assistant if isinstance(assistant, dict) else {}
    error = schemas.get("StructuredOutputError")
    error = error if isinstance(error, dict) else {}
    text_part = schemas.get("TextPartInput")
    text_part = text_part if isinstance(text_part, dict) else {}

    return {
        "session_request_properties": _name_set(
            session_post.get("request_body_properties")
        ),
        "session_response_200_ref": session_post.get("response_200_ref"),
        "message_operation_id": message_post.get("operation_id"),
        "message_request_properties": _name_set(
            message_post.get("request_body_properties")
        ),
        "message_request_required": _name_set(message_post.get("request_body_required")),
        "message_response_required": _name_set(
            message_post.get("response_200_required")
        ),
        "message_info_ref": refs.get("info"),
        "output_format_properties": _name_set(out_format.get("properties")),
        "output_format_required": _name_set(out_format.get("required")),
        "output_format_type_enum": _name_set(out_format.get("type_enum")),
        "output_format_schema_ref": out_format.get("schema_ref"),
        "permission_rule_properties": _name_set(permission_rule.get("properties")),
        "permission_rule_required": _name_set(permission_rule.get("required")),
        "permission_action_enum": _name_set(permission_rule.get("action_enum")),
        "assistant_properties": _name_set(assistant.get("properties")),
        "assistant_required": _name_set(assistant.get("required")),
        "assistant_additional_properties": assistant.get("additionalProperties"),
        "structured_error_properties": _name_set(error.get("properties")),
        "structured_error_required": _name_set(error.get("required")),
        "structured_error_name_enum": _name_set(error.get("name_enum")),
        "structured_error_data_properties": _name_set(error.get("data_properties")),
        "structured_error_data_required": _name_set(error.get("data_required")),
        "text_part_properties": _name_set(text_part.get("properties")),
        "text_part_required": _name_set(text_part.get("required")),
        "text_part_type_enum": _name_set(text_part.get("type_enum")),
    }


def _diff_facts(committed: dict[str, Any], live: dict[str, Any]) -> list[str]:
    """Every pointer whose committed fact differs from the live fact."""
    return [
        f"{pointer}: committed={committed[pointer]!r} live={live.get(pointer)!r}"
        for pointer in sorted(committed)
        if committed[pointer] != live.get(pointer)
    ]


# --- the operator lane ---------------------------------------------------------


async def test_live_doc_matches_the_committed_slice() -> None:
    """One `GET /doc` + one `GET /global/health`; no LLM call (D-57)."""
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
        spec_response = await client.get(contract.DOC_PATH)
        spec_response.raise_for_status()
        spec: dict[str, Any] = spec_response.json()
        # P12: /doc's `info.version` is a static spec version (1.0.0). The RUNNING
        # server version lives only on /global/health, so read it there.
        health: dict[str, Any] = (await client.get(GLOBAL_HEALTH_PATH)).json()

    # D-57 / T-3-12: spec fetch + diff only. Structurally no POST can occur.
    assert observed, "no request was recorded — the no-call guard would be vacuous"
    assert {method for method, _ in observed} == {"GET"}
    assert all(not path.startswith("/session") for _, path in observed)

    diffs = _diff_facts(_committed_facts(fixture), _live_facts(spec))
    assert diffs == [], (
        "opencode /doc has drifted from the committed slice. Confirm the drift is "
        "real (read each pointer above), then refresh "
        "tests/llm/fixtures/opencode-doc.json DELIBERATELY via "
        f"docs/runbook-opencode-contract.md. Divergent pointers: {diffs}"
    )

    assert health.get("version") == fixture["_meta"]["server_version"], (
        "the running server version changed: refresh the fixture deliberately and "
        f"record the observed GET /global/health version ({health.get('version')!r}) "
        f"in _meta.server_version (currently "
        f"{fixture['_meta']['server_version']!r})"
    )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-m", "live"])
