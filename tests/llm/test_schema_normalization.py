"""The wire-schema normalization: `const`→`enum`, `discriminator` dropped.

The existing contract tests only exercise clean schemas (`ProbeResult`,
`RankingResponse`), so they would FALSE-PASS on this bug. These tests go through
`to_message_body(schema=TailoringPatch, ...)` — the real failing call — and prove
the emitted schema is the plain subset the provider honors while everything the
working ranking call relies on (`$defs`/`$ref`/`oneOf`/`additionalProperties`)
survives untouched.

The raw-schema guard at the top is load-bearing: it proves `TailoringPatch`
genuinely carries `const`/`discriminator`, so the rest of the file asserts the
normalization did work rather than asserting on an already-clean schema.
"""

from __future__ import annotations

from typing import Any

from app.domain.cv import TailoringPatch
from app.domain.schemas.ranking import RankingResponse
from app.llm.builders import _normalize_json_schema, to_message_body
from app.llm.contract import FORMAT_FIELD, FORMAT_SCHEMA_FIELD


def _emitted_schema() -> dict[str, Any]:
    """The schema actually placed on the wire for `TailoringPatch`."""
    body = to_message_body(
        schema=TailoringPatch,
        system="system",
        parts=["user content"],
        provider_id="provider",
        model_id="model",
    )
    return body[FORMAT_FIELD][FORMAT_SCHEMA_FIELD]


def _find_keys(node: object, name: str) -> list[object]:
    """Every value under a key `name`, at any nesting depth. Proves absence."""
    found: list[object] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == name:
                found.append(value)
            found.extend(_find_keys(value, name))
    elif isinstance(node, list):
        for item in node:
            found.extend(_find_keys(item, name))
    return found


def test_the_raw_patch_schema_really_carries_const_and_discriminator() -> None:
    """Guard: without this, the assertions below could pass vacuously."""
    raw = TailoringPatch.model_json_schema()
    assert _find_keys(raw, "const"), "TailoringPatch no longer emits `const` — retune this test"
    assert _find_keys(raw, "discriminator"), (
        "TailoringPatch no longer emits `discriminator` — retune this test"
    )


def test_the_emitted_schema_has_no_const_or_discriminator_anywhere() -> None:
    emitted = _emitted_schema()
    assert _find_keys(emitted, "const") == []
    assert _find_keys(emitted, "discriminator") == []


def test_each_op_discriminator_survived_as_a_single_value_enum() -> None:
    emitted = _emitted_schema()
    expected = {
        "BulletMove": "move_bullet",
        "BulletWeight": "reweight_bullet",
        "DemoteBullet": "demote_bullet",
        "DropBullet": "drop_bullet",
        "ReorderSection": "reorder_section",
    }
    for def_name, op_value in expected.items():
        op_prop = emitted["$defs"][def_name]["properties"]["op"]
        assert op_prop["enum"] == [op_value], (def_name, op_prop)
        assert "const" not in op_prop, def_name


def test_the_structure_ranking_relies_on_is_preserved() -> None:
    raw = TailoringPatch.model_json_schema()
    emitted = _emitted_schema()

    # $defs still present and still referenced by $ref (not inlined).
    assert emitted["$defs"] == {
        name: _normalize_json_schema(raw["$defs"][name]) for name in raw["$defs"]
    }
    refs = _find_keys(emitted, "$ref")
    for def_name in raw["$defs"]:
        assert f"#/$defs/{def_name}" in refs, def_name

    # The discriminated union is still a `oneOf` over the same refs.
    op_defs = ("BulletMove", "BulletWeight", "DemoteBullet", "DropBullet", "ReorderSection")
    ops_items = emitted["properties"]["ops"]["items"]
    assert [entry["$ref"] for entry in ops_items["oneOf"]] == [
        f"#/$defs/{name}" for name in op_defs
    ]

    # The fabrication-safety control and the required lists are untouched.
    assert emitted["additionalProperties"] is False
    assert emitted["required"] == raw["required"]
    for def_name in raw["$defs"]:
        emitted_def = emitted["$defs"][def_name]
        assert emitted_def["required"] == raw["$defs"][def_name]["required"], def_name
        assert emitted_def["additionalProperties"] is False, def_name


def test_normalization_is_idempotent() -> None:
    raw = TailoringPatch.model_json_schema()
    once = _normalize_json_schema(raw)
    assert _normalize_json_schema(once) == once


def test_normalization_is_a_noop_on_a_clean_schema() -> None:
    raw = RankingResponse.model_json_schema()
    # Verify the chosen control genuinely has nothing to normalize.
    assert _find_keys(raw, "const") == []
    assert _find_keys(raw, "discriminator") == []
    assert _normalize_json_schema(raw) == raw


def test_recursion_reaches_const_nested_in_lists() -> None:
    node = {"anyOf": [{"properties": {"x": {"const": 1}}}]}
    assert _normalize_json_schema(node) == {"anyOf": [{"properties": {"x": {"enum": [1]}}}]}
