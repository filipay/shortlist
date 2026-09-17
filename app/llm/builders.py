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
    verbatim — the caller supplies a constant. `retryCount` is added only when
    `retry_count` is not None (it is OPTIONAL on the wire). `tools` is added only
    when explicitly supplied; the port's default is deny-by-omission and the
    documented deny encoding lands in plan 03-06 (Pitfall P5).
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
    if tools is not None:
        body["tools"] = dict(tools)
    return body


__all__ = ["to_message_body", "to_message_parts"]
