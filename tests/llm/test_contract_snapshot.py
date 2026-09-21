"""PLAT-05 / D-53..D-57 — the committed `/doc` slice and its default-lane contract.

The three-step proof chain this module participates in:

    builder == snapshot    <-- THIS FILE (default lane, no server running)
    snapshot == live spec  <-- tests/llm/test_contract_live.py (operator `-m live`)
    the real call works    <-- POST /settings/llm-test (plan 03-01's selftest)

Everything here reads `tests/llm/fixtures/opencode-doc.json`, a **hand-written
projection** of the installed opencode spec's structured-output slice (D-55): a
fixed set of list-valued facts, so unrelated OpenAPI churn cannot fail the test.
The slice's only sanctioned refresh path is `docs/runbook-opencode-contract.md`.

There is exactly ONE pinned name per surface (D-54). An adaptive client that
"accepts either `format` or `outputFormat`" is explicitly rejected, so the
negative control below asserts the wrong spellings are absent from the raw
fixture text where no pointer walk could miss them.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from app.domain.schemas.probe import ProbeResult
from app.llm import contract
from app.llm.builders import to_message_body

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "opencode-doc.json"
PYPROJECT_PATH = Path(__file__).resolve().parents[2] / "pyproject.toml"

#: Spellings the published docs use and the live server does NOT. D-54 forbids
#: accepting any of them; they are the negative control's subject.
WRONG_NAMES = ("outputFormat", "structured_output", "structuredOutput")


def _load_fixture() -> dict[str, Any]:
    """The committed slice, or a loud assertion naming the refresh runbook.

    Asserting existence (rather than letting `read_text` raise) keeps a missing
    or renamed fixture an assertion failure with the fix in the message.
    """
    assert FIXTURE_PATH.exists(), (
        f"missing {FIXTURE_PATH} — it is the committed contract slice; refresh it "
        "deliberately via docs/runbook-opencode-contract.md"
    )
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _message_post(fixture: dict[str, Any]) -> dict[str, Any]:
    """The message-send POST object, indexed by the OpenAPI path spelling.

    Indexing by the constant (not a literal) is deliberate: the fixture's key is
    `contract.MESSAGE_DOC_PATH`, and `test_the_path_constants_are_real_fixture_keys`
    proves it is present before any other test indexes it.
    """
    return fixture["paths"][contract.MESSAGE_DOC_PATH]["post"]


def _missing_pointers(
    fixture: dict[str, Any], *, request_field: str, response_field: str
) -> list[str]:
    """The pointers that fail the contract, `[]` when the slice agrees.

    One reusable helper so the guard-can-fail companion exercises the SAME code
    path the real assertion uses (a guard that cannot fail is not a guard).
    """
    missing: list[str] = []
    if request_field not in _message_post(fixture)["request_body_properties"]:
        missing.append(
            f"paths[{contract.MESSAGE_DOC_PATH}].post.request_body_properties"
        )
    assistant_properties = fixture["components"]["schemas"]["AssistantMessage"][
        "properties"
    ]
    if response_field not in assistant_properties:
        missing.append("components.schemas.AssistantMessage.properties")
    return missing


def _missing_permission_pointers(
    fixture: dict[str, Any], *, fields: tuple[str, ...], action: str
) -> list[str]:
    """The deny-rule pointers that fail the pin, `[]` when the slice agrees.

    Mirrors `_missing_pointers`: one reusable helper so the guard-can-fail
    companion exercises the SAME code path the real assertion uses (a guard that
    cannot fail is not a guard). The rule's inner field names and its action enum
    are exactly what a server-side rename would move, so a rename must produce a
    named failing pointer here rather than silently un-denying tools.
    """
    missing: list[str] = []
    schema = fixture["components"]["schemas"]["PermissionRule"]
    properties = set(schema["properties"])
    required = set(schema["required"])
    actions = set(schema["action_enum"])
    for field in fields:
        if field not in properties:
            missing.append(f"components.schemas.PermissionRule.properties[{field}]")
        if field not in required:
            missing.append(f"components.schemas.PermissionRule.required[{field}]")
    if action not in actions:
        missing.append(f"components.schemas.PermissionRule.action_enum[{action}]")
    return missing


# --- the fixture's own index ---------------------------------------------------


def test_the_path_constants_are_real_fixture_keys() -> None:
    """No test may index the fixture by MESSAGE_PATH — only by the spec spelling."""
    fixture = _load_fixture()
    paths = fixture["paths"]

    assert contract.SESSION_PATH in paths
    assert contract.MESSAGE_DOC_PATH in paths
    # The two constants exist on purpose and are NOT the same key: one is our
    # wire spelling, the other is the spec's path-template spelling.
    assert contract.MESSAGE_PATH != contract.MESSAGE_DOC_PATH


def test_the_meta_records_the_observed_server_and_the_spec_source() -> None:
    fixture = _load_fixture()
    meta = fixture["_meta"]

    assert meta["server_version"], "the fixture must record the observed server version"
    assert meta["captured_at"]
    assert contract.DOC_PATH in meta["source"]
    assert meta["spec_openapi"]
    # P12: /doc's info.version is a static spec version, not the server version.
    assert "static spec version" in meta["note"]


# --- the request-side contract -------------------------------------------------


def test_the_request_side_contract_matches_the_snapshot() -> None:
    fixture = _load_fixture()
    post = _message_post(fixture)

    assert contract.FORMAT_FIELD in post["request_body_properties"]
    assert post["request_body_required"] == [contract.MESSAGE_REQUIRED_FIELDS[0]]
    assert isinstance(post["operation_id"], str) and post["operation_id"]


def test_the_format_object_inner_contract_matches_the_snapshot() -> None:
    fixture = _load_fixture()
    schema = fixture["components"]["schemas"]["OutputFormatJsonSchema"]

    assert set(contract.FORMAT_INNER_KEYS) <= set(schema["properties"])
    assert list(contract.FORMAT_REQUIRED_KEYS) == schema["required"]
    assert contract.FORMAT_JSON_SCHEMA_TYPE in schema["type_enum"]


def test_the_session_contract_matches_the_snapshot() -> None:
    fixture = _load_fixture()
    session = fixture["paths"][contract.SESSION_PATH]["post"]

    assert isinstance(session["request_body_properties"], list)
    assert session["response_200_ref"]


def test_the_permission_deny_rule_contract_matches_the_snapshot() -> None:
    """The enforced tool deny is pinned by NAME (T-3-25), not by assumption.

    A server-side rename of `permission`/`pattern`/`action` or a drop of the
    `deny` action must fail this default-lane test with no server running, so it
    cannot silently turn `DEFAULT_DENY_RULES` into a no-op.
    """
    fixture = _load_fixture()
    session = fixture["paths"][contract.SESSION_PATH]["post"]
    schema = fixture["components"]["schemas"]["PermissionRule"]

    assert contract.PERMISSION_FIELD in session["request_body_properties"]
    assert set(contract.PERMISSION_RULE_FIELDS) <= set(schema["properties"])
    assert set(contract.PERMISSION_RULE_FIELDS) <= set(schema["required"])
    assert contract.PERMISSION_DENY_ACTION in schema["action_enum"]
    assert (
        _missing_permission_pointers(
            fixture,
            fields=contract.PERMISSION_RULE_FIELDS,
            action=contract.PERMISSION_DENY_ACTION,
        )
        == []
    )


# --- the response-side contract ------------------------------------------------


def test_the_response_side_contract_matches_the_snapshot() -> None:
    fixture = _load_fixture()
    schemas = fixture["components"]["schemas"]
    assistant = schemas["AssistantMessage"]
    error = schemas["StructuredOutputError"]

    assert contract.STRUCTURED_RESPONSE_PATH[-1] in assistant["properties"]
    assert contract.STRUCTURED_ERROR_NAME in error["name_enum"]
    assert contract.STRUCTURED_ERROR_RETRIES_PATH[-1] in error["data_properties"]
    assert contract.STRUCTURED_ERROR_MESSAGE_PATH[-1] in error["data_properties"]
    # The identity fields the port records per call (D-12) are real spec fields.
    assert set(contract.MESSAGE_MODEL_FIELDS) <= set(assistant["properties"])
    # The envelope's parent (`info.error`) is a real AssistantMessage property.
    assert contract.STRUCTURED_ERROR_RETRIES_PATH[1] in assistant["properties"]
    assert contract.STRUCTURED_RESPONSE_PATH[0] in _message_post(fixture)[
        "response_200_required"
    ]


def test_the_text_part_contract_matches_the_snapshot() -> None:
    fixture = _load_fixture()
    text_part = fixture["components"]["schemas"]["TextPartInput"]

    assert list(contract.TEXT_PART_FIELDS) == text_part["required"]
    assert contract.TEXT_PART_TYPE in text_part["type_enum"]


# --- the negative control (D-54) ----------------------------------------------


def test_the_documented_alternative_spellings_are_absent_from_the_snapshot() -> None:
    """Over the RAW fixture text, so no pointer walk can miss a stray spelling."""
    raw = FIXTURE_PATH.read_text(encoding="utf-8")

    for wrong in WRONG_NAMES:
        assert wrong not in raw, (
            f"{wrong!r} appears in the fixture — the pinned name is "
            f"{contract.FORMAT_FIELD!r} / {contract.STRUCTURED_RESPONSE_PATH[-1]!r}; "
            "an adaptive 'accept either name' client is explicitly rejected (D-54)"
        )
    # The pinned names themselves are not alternatives.
    assert contract.FORMAT_FIELD not in WRONG_NAMES
    assert contract.STRUCTURED_RESPONSE_PATH[-1] not in WRONG_NAMES


# --- the builder emits only what the snapshot allows ---------------------------


def test_the_builder_emits_only_snapshot_request_properties() -> None:
    fixture = _load_fixture()
    allowed = set(_message_post(fixture)["request_body_properties"])

    body = to_message_body(
        schema=ProbeResult,
        system="a constant",
        parts=["untrusted"],
        provider_id="opencode-go",
        model_id="deepseek-v4.1-flash",
        retry_count=2,
    )

    assert set(body) <= allowed, "the builder emits a key the server does not accept"
    assert tuple(body["model"]) == contract.MESSAGE_MODEL_FIELDS
    assert contract.FORMAT_FIELD in body


# --- a guard that cannot fail is not a guard -----------------------------------


def test_the_pointer_check_can_actually_fail() -> None:
    fixture = _load_fixture()

    assert (
        _missing_pointers(
            fixture,
            request_field=contract.FORMAT_FIELD,
            response_field=contract.STRUCTURED_RESPONSE_PATH[-1],
        )
        == []
    )
    wrong = _missing_pointers(
        fixture,
        request_field=WRONG_NAMES[0],
        response_field=WRONG_NAMES[1],
    )
    assert wrong, "the pointer check passed a deliberately wrong name — it has no teeth"


def test_the_permission_pointer_check_can_actually_fail() -> None:
    """The deny-rule pin must reject decoy names AND a decoy action."""
    fixture = _load_fixture()

    assert (
        _missing_permission_pointers(
            fixture,
            fields=contract.PERMISSION_RULE_FIELDS,
            action=contract.PERMISSION_DENY_ACTION,
        )
        == []
    )
    wrong = _missing_permission_pointers(
        fixture,
        fields=("perm", "pattern_name"),
        action="allow_only",
    )
    assert wrong, (
        "the permission pointer check passed deliberately wrong rule fields/action "
        "— it has no teeth"
    )


# --- the default lane structurally cannot run the live lane --------------------


def test_the_default_lane_cannot_run_the_live_lane() -> None:
    """This guard lives here, not in the live module: a guard inside a live-marked
    module would never execute in the default lane."""
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    ini_options = config["tool"]["pytest"]["ini_options"]

    # The exclusion is additive (Phase 4 widened it to `not live and not latex`),
    # so assert the `live` lane is still deselected rather than freeze the whole
    # addopts string.
    assert "not live" in ini_options["addopts"]
    assert any(str(marker).startswith("live:") for marker in ini_options["markers"])


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__])
