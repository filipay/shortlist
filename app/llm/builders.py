"""Pure request builders for the opencode wire — no I/O, no state.

The **purity contract** is what lets `tests/llm/test_contract_snapshot.py` and
the tracer test pin the request vocabulary with no server running: two identical
calls produce equal bodies, and a rename fails a default-lane test.

**Deliberate port-vs-wire translation.** At the PORT boundary `parts` is a plain
`list[str]` (ergonomic for callers); on the WIRE each string becomes a
`TextPartInput` object — `{"type": "text", "text": "..."}`. The opencode spec
requires `type` and `text` and forbids extras, and a raw string is an immediate
422. **Do not "fix" this into raw strings** — the translation is pinned by tests.

Every structured-output wire name comes from `app.llm.contract`, so a rename is
a one-line change there (D-54). `system` is a caller-supplied constant: this
module interpolates nothing into it, and no argument lets request-derived data
reach it (§6.3 / m5).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from app.llm.contract import (
    FORMAT_FIELD,
    FORMAT_JSON_SCHEMA_TYPE,
    FORMAT_RETRY_FIELD,
    FORMAT_SCHEMA_FIELD,
    FORMAT_TYPE_FIELD,
    MESSAGE_MODEL_FIELDS,
    MESSAGE_REQUIRED_FIELDS,
    MESSAGE_TOOLS_FIELD,
    PERMISSION_FIELD,
    PERMISSION_WILDCARD,
    SESSION_MODEL_FIELDS,
    TEXT_PART_FIELDS,
    TEXT_PART_TYPE,
)


def to_message_parts(texts: Sequence[str]) -> list[dict[str, str]]:
    """Wrap each port-level string as a wire `TextPartInput`.

    `TEXT_PART_FIELDS` names the two keys and `TEXT_PART_TYPE` the enum value, so
    the wire spelling has exactly one home.
    """
    return [
        {TEXT_PART_FIELDS[0]: TEXT_PART_TYPE, TEXT_PART_FIELDS[1]: text}
        for text in texts
    ]


def to_message_body(
    *,
    schema: type[BaseModel],
    system: str,
    parts: Sequence[str],
    provider_id: str,
    model_id: str,
    agent: str | None = None,
    retry_count: int | None = None,
    tools: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    """Emit EXACTLY the wire shape. Every key name comes from `app.llm.contract`.

    `parts` is the only channel for untrusted content. `system` is passed through
    verbatim — the caller supplies a constant, and no argument of this function can
    alter it.

    **`tools` policy (Pitfall P5).** `tools` is a `Mapping[str, bool]` of explicit
    per-name GRANTS. `None` or an empty mapping emits NO key at all — an
    undocumented empty map is not a deny, so it is never sent. A `"*"` key raises
    `ValueError`: the deprecated `tools` map's wildcard semantics are undocumented
    (the `"*"` wildcard is a `permission` key, not a `tools` key). The ENFORCED deny
    is the session-level `permission` ruleset built by `to_session_body`, which the
    server documents as the control to use.

    `retryCount` is added only when `retry_count` is not None (OPTIONAL on the wire).
    """
    body: dict[str, Any] = {
        MESSAGE_REQUIRED_FIELDS[0]: to_message_parts(parts),
        "system": system,
        "model": {
            MESSAGE_MODEL_FIELDS[0]: provider_id,
            MESSAGE_MODEL_FIELDS[1]: model_id,
        },
        FORMAT_FIELD: {
            FORMAT_TYPE_FIELD: FORMAT_JSON_SCHEMA_TYPE,
            FORMAT_SCHEMA_FIELD: schema.model_json_schema(),
        },
    }
    if retry_count is not None:
        body[FORMAT_FIELD][FORMAT_RETRY_FIELD] = retry_count
    if agent is not None:
        body["agent"] = agent
    if tools:
        if PERMISSION_WILDCARD in tools:
            raise ValueError(
                f"the deprecated {MESSAGE_TOOLS_FIELD!r} map does not support a "
                f"{PERMISSION_WILDCARD!r} wildcard (its semantics are undocumented); "
                f"use the session {PERMISSION_FIELD!r} ruleset for the enforced deny"
            )
        body[MESSAGE_TOOLS_FIELD] = {
            name: bool(granted) for name, granted in tools.items()
        }
    return body


def to_session_body(
    *,
    provider_id: str,
    model_id: str,
    permission: Sequence[Mapping[str, str]] | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Emit the `POST /session` body — whose `model` shape is the INVERSE.

    The live 1.18.31 `POST /session` takes
    ``model: {"id": <modelID>, "providerID": <providerID>}`` (research §1), i.e. the
    **model id under `id`** and the **provider id under `providerID`**. The message
    body is ``{"providerID": <providerID>, "modelID": <modelID>}``. Both objects are
    ``additionalProperties: false``, so a wrong placement is a silent 400 — and the
    two shapes look deceptively similar, which is why
    `tests/llm/test_trust_boundary.py` asserts both key sets AND both value
    placements together. **Do not collapse or invert them.**

    `permission` is the DOCUMENTED tool control (`tools` is deprecated): an array of
    `PermissionRule` objects, each `{permission, pattern, action}`. `title` is
    optional. This builder emits no untrusted content: nothing here comes from a
    listing.
    """
    body: dict[str, Any] = {
        "model": {
            SESSION_MODEL_FIELDS[0]: model_id,
            SESSION_MODEL_FIELDS[1]: provider_id,
        },
    }
    if title is not None:
        body["title"] = title
    if permission is not None:
        body[PERMISSION_FIELD] = [dict(rule) for rule in permission]
    return body


__all__ = ["to_message_body", "to_message_parts", "to_session_body"]
