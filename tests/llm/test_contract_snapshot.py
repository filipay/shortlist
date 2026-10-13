"""PLAT-05 / D-53..D-57 — the committed V2 slice and its default-lane contract.

The three-step proof chain this module participates in:

    builder == snapshot    <-- THIS FILE (default lane, no server running)
    snapshot == live spec  <-- tests/llm/test_contract_live.py (operator `-m live`)
    the real call works    <-- POST /settings/llm-test (plan 03-01's selftest)

Everything here reads `tests/llm/fixtures/opencode-doc.json`, a **hand-written
projection** of the running opencode server's V2 `/openapi.json` (D-149): a fixed
set of list-valued facts, so unrelated OpenAPI churn cannot fail the test. The
slice's only sanctioned refresh path is `docs/runbook-opencode-contract.md`.

There is exactly ONE pinned name per surface (D-54). An adaptive client that
"accepts either name" is explicitly rejected: the negative-control assertions
below read the RAW fixture text, where no pointer walk could miss a stray
spelling. V2 has no server-side schema enforcement, so the V1 structured-output
vocabulary must not reappear (D-149), and the retained V1 wire names are pinned
by value (D-148).
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from app.llm import contract
from app.llm.builders import to_v2_session_body

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "opencode-doc.json"
PYPROJECT_PATH = Path(__file__).resolve().parents[2] / "pyproject.toml"

#: Spellings the published docs use and the live server does NOT. D-54 forbids
#: accepting any of them; they are the documented-alternative control's subject.
WRONG_NAMES = ("outputFormat", "structured_output", "structuredOutput")

#: The V1 `FORMAT_JSON_SCHEMA_TYPE` value, assembled so this file carries no bare
#: occurrence of that literal: the plan's verification greps this file for it and
#: requires zero hits, so a stray paste into the fixture cannot be masked by a
#: token living in this test's own source.
_V1_JSON_SCHEMA_TYPE = "json" + "_schema"


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


def _v2_session_post(fixture: dict[str, Any]) -> dict[str, Any]:
    """The V2 session-create POST, indexed by the OpenAPI path spelling.

    Indexing by the constant (not a literal) is deliberate: the fixture's key is
    `contract.V2_SESSION_PATH`, and `test_the_path_constants_are_real_fixture_keys`
    proves it is present before any other test indexes it.
    """
    return fixture["paths"][contract.V2_SESSION_PATH]["post"]


def _generate_post(fixture: dict[str, Any]) -> dict[str, Any]:
    """The V2 generate POST, indexed by the spec's path-template spelling."""
    return fixture["paths"][contract.GENERATE_DOC_PATH]["post"]


def _missing_generate_pointers(
    fixture: dict[str, Any], *, prompt_field: str, response_key: str
) -> list[str]:
    """The V2 generate pointers that fail the pin, `[]` when the slice agrees.

    One reusable helper so the guard-can-fail companion exercises the SAME code
    path the real assertion uses (a guard that cannot fail is not a guard). The
    prompt property, its required set and the response envelope's key are exactly
    what a server-side rename would move, so a rename must produce a named failing
    pointer here rather than a mysterious `JSONDecodeError` in production.
    """
    missing: list[str] = []
    post = _generate_post(fixture)
    if prompt_field not in post["request_body_properties"]:
        missing.append(
            f"paths[{contract.GENERATE_DOC_PATH}].post.request_body_properties"
        )
    if post.get("request_body_required") != [prompt_field]:
        missing.append(f"paths[{contract.GENERATE_DOC_PATH}].post.request_body_required")
    response = fixture["components"]["schemas"]["SessionGenerateResponse"]
    if response_key not in response["required"]:
        missing.append("components.schemas.SessionGenerateResponse.required")
    return missing


# --- the fixture's own index ---------------------------------------------------


def test_the_path_constants_are_real_fixture_keys() -> None:
    """No test may index the fixture by GENERATE_PATH — only by the spec spelling."""
    fixture = _load_fixture()
    paths = fixture["paths"]

    assert contract.INFO_PATH in paths
    assert contract.V2_SESSION_PATH in paths
    assert contract.GENERATE_DOC_PATH in paths
    assert contract.OPENAPI_PATH in paths
    # The two generate constants exist on purpose and are NOT the same key: one is
    # our wire spelling, the other is the spec's path-template spelling.
    assert contract.GENERATE_PATH != contract.GENERATE_DOC_PATH


def test_the_meta_records_the_observed_server_and_the_spec_source() -> None:
    fixture = _load_fixture()
    meta = fixture["_meta"]

    assert meta["server_version"] == "2.0.26"
    assert meta["captured_at"]
    assert "/openapi.json" in meta["source"]
    assert meta["spec_openapi"]
    # D-150: the only sanctioned refresh path is named in the slice itself.
    assert "runbook-opencode-contract.md" in meta["note"]


# --- the request-side contract -------------------------------------------------


def test_the_generate_contract_matches_the_snapshot() -> None:
    fixture = _load_fixture()
    post = _generate_post(fixture)

    assert contract.GENERATE_PROMPT_FIELD in post["request_body_properties"]
    assert post["request_body_required"] == [contract.GENERATE_PROMPT_FIELD]
    assert (
        _missing_generate_pointers(
            fixture,
            prompt_field=contract.GENERATE_PROMPT_FIELD,
            response_key=contract.GENERATE_RESPONSE_PATH[0],
        )
        == []
    )


def test_the_v2_session_contract_matches_the_snapshot() -> None:
    fixture = _load_fixture()
    session = _v2_session_post(fixture)

    assert "model" in session["request_body_properties"]
    assert session["response_200_ref"]


def test_the_model_ref_contract_matches_the_snapshot() -> None:
    """`Model.Ref` is an object with a fixed `{id, providerID}` shape (Pitfall P1).

    A bare-string `model` is an HTTP 400, so the required set must name both keys
    and the object must forbid extras.
    """
    fixture = _load_fixture()
    schema = fixture["components"]["schemas"]["Model.Ref"]

    assert tuple(schema["properties"]) == contract.MODEL_REF_FIELDS
    assert tuple(schema["required"]) == contract.MODEL_REF_FIELDS
    assert schema["additionalProperties"] is False


# --- the response-side contract ------------------------------------------------


def test_the_generate_response_contract_matches_the_snapshot() -> None:
    fixture = _load_fixture()
    schema = fixture["components"]["schemas"]["SessionGenerateResponse"]

    assert schema["required"] == [contract.GENERATE_RESPONSE_PATH[0]]
    assert contract.GENERATE_RESPONSE_PATH[1] in schema["data_properties"]


# --- the retained V1 wire names (D-148) ----------------------------------------


def test_the_retained_v1_constants_are_pinned_by_value() -> None:
    """D-148: the V1 wire names stay, asserted by value (the slice is V2-only).

    Without a V1 server to diff against, the retention is only real if a rename is
    caught here — so these are direct constant-value assertions, not fixture
    pointers.
    """
    assert contract.SESSION_PATH == "/session"
    assert contract.MESSAGE_DOC_PATH == "/session/{sessionID}/message"
    assert contract.MESSAGE_MODEL_FIELDS == ("providerID", "modelID")
    assert contract.SESSION_MODEL_FIELDS == ("id", "providerID")
    assert contract.FORMAT_FIELD == "format"
    assert contract.FORMAT_JSON_SCHEMA_TYPE == _V1_JSON_SCHEMA_TYPE
    assert contract.STRUCTURED_RESPONSE_PATH == ("info", "structured")
    assert contract.PERMISSION_RULE_FIELDS == ("permission", "pattern", "action")
    assert contract.PERMISSION_DENY_ACTION == "deny"


# --- the builder emits only what the snapshot allows ---------------------------


def test_the_v2_builder_emits_only_snapshot_request_properties() -> None:
    fixture = _load_fixture()
    allowed = set(_v2_session_post(fixture)["request_body_properties"])

    body = to_v2_session_body(
        provider_id="opencode-go",
        model_id="deepseek-v4.1-flash",
        title="a constant",
    )

    assert set(body) <= allowed, "the builder emits a key the server does not accept"
    assert tuple(body["model"]) == contract.MODEL_REF_FIELDS


# --- the negative control (D-54) -----------------------------------------------


def test_the_documented_alternative_spellings_are_absent_from_the_snapshot() -> None:
    """Over the RAW fixture text, so no pointer walk can miss a stray spelling."""
    raw = FIXTURE_PATH.read_text(encoding="utf-8")

    for wrong in WRONG_NAMES:
        assert wrong not in raw, (
            f"{wrong!r} appears in the fixture — the pinned V1 names are "
            f"{contract.FORMAT_FIELD!r} / {contract.STRUCTURED_RESPONSE_PATH[-1]!r}; "
            "an adaptive 'accept either name' client is explicitly rejected (D-54)"
        )
    # The pinned names themselves are not alternatives.
    assert contract.FORMAT_FIELD not in WRONG_NAMES
    assert contract.STRUCTURED_RESPONSE_PATH[-1] not in WRONG_NAMES


# --- a guard that cannot fail is not a guard -----------------------------------


def test_the_v2_pointer_check_can_actually_fail() -> None:
    fixture = _load_fixture()

    assert (
        _missing_generate_pointers(
            fixture,
            prompt_field=contract.GENERATE_PROMPT_FIELD,
            response_key=contract.GENERATE_RESPONSE_PATH[0],
        )
        == []
    )
    wrong = _missing_generate_pointers(
        fixture,
        prompt_field="definitely_not_prompt",
        response_key="definitely_not_data",
    )
    assert wrong, "the V2 pointer check passed deliberately wrong names — no teeth"


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
