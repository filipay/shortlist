"""PLAT-02 / M1 — the salvage path: partial JSON, tolerated errors only.

A structured response can arrive truncated, or with one field the model spelled
unexpectedly. The naive handler lets the `ValidationError` propagate (killing the
run) or silently stores a partial dict; PITFALLS M1 is exactly that failure mode.

The strategy: `pydantic_core.from_json(..., allow_partial=True)` drops a truncated
tail, and a `WrapValidator` substitutes a field default **only** for an explicit
allow-list of tolerated error types. "Any error" is forbidden — it would launder a
genuine schema mismatch into a silently-empty result, which is indistinguishable
from a real low score to Phase 5's ranking.

`_salvage` and `TOLERATED_SCHEMA_ERRORS` are addressed through the module so the
target tests fail on a clear assertion when the implementation is absent.
"""

from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, ValidationError, WrapValidator
from pydantic_core import PydanticUseDefault

from app.domain.schemas.probe import ProbeResult
from app.llm import opencode_server
from tests.llm.test_complete_structured import LIVE_MESSAGE_BODY, Recorder, _backend


def _salvage(schema: type, payload: object) -> object:
    """The production salvage helper, asserted present so RED fails loudly."""
    assert hasattr(opencode_server, "_salvage"), (
        "app.llm.opencode_server._salvage is not implemented yet"
    )
    return opencode_server._salvage(schema, payload)


def _tolerated() -> frozenset[str]:
    assert hasattr(opencode_server, "TOLERATED_SCHEMA_ERRORS"), (
        "app.llm.opencode_server.TOLERATED_SCHEMA_ERRORS is not implemented yet"
    )
    return opencode_server.TOLERATED_SCHEMA_ERRORS


# --- truncated and missing payloads --------------------------------------------


def test_a_truncated_json_string_salvages_with_the_readable_fields_intact() -> None:
    truncated = '{"acknowledged": true, "echo": "ok", "extra": tru'

    result = _salvage(ProbeResult, truncated)

    assert isinstance(result, ProbeResult)
    assert result.acknowledged is True
    assert result.echo == "ok"
    # The dropped tail falls back to the field default rather than raising.
    assert result.instruction_detected is False


def test_a_payload_with_a_missing_defaulted_field_validates_to_defaults() -> None:
    result = _salvage(ProbeResult, {})

    assert result == ProbeResult()
    assert result.acknowledged is False


# --- the allow-list has teeth --------------------------------------------------


def test_an_untolerated_schema_mismatch_is_not_salvaged() -> None:
    """`int_type` is NOT in the allow-list: a genuine mismatch must fail loudly."""

    class Strict(BaseModel):
        count: int = 0

    with pytest.raises(ValidationError) as excinfo:
        _salvage(Strict, {"count": {"nested": 1}})

    assert [error["type"] for error in excinfo.value.errors()] == ["int_type"]


def test_the_tolerated_error_allow_list_is_exact() -> None:
    tolerated = _tolerated()

    assert isinstance(tolerated, frozenset)
    assert tolerated == frozenset({"missing", "int_parsing"})


def test_the_allow_list_is_load_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A guard that cannot fail is not a guard: widening the list changes the outcome."""

    class Strict(BaseModel):
        count: int = 0

    payload = {"count": {"nested": 1}}
    with pytest.raises(ValidationError):
        _salvage(Strict, payload)

    monkeypatch.setattr(
        opencode_server, "TOLERATED_SCHEMA_ERRORS", frozenset({"int_type"})
    )

    assert _salvage(Strict, payload) == Strict()


def test_salvage_does_not_mutate_the_callers_payload() -> None:
    payload = {"acknowledged": True, "echo": "ok"}
    snapshot = dict(payload)

    _salvage(ProbeResult, payload)

    assert payload == snapshot


# --- the no-default pitfall (P11) ----------------------------------------------


def _use_default_for_unusable(value: object, handler: object) -> object:
    if value == "unusable":
        return PydanticUseDefault()
    return handler(value)  # type: ignore[operator]


def test_pydantic_use_default_leaks_on_a_field_with_no_default() -> None:
    """P11: `PydanticUseDefault()` substitutes a DEFAULT.

    On a required field with no default the marker object itself becomes the value
    — which is exactly why every tolerated field must declare a default. This test
    pins the pitfall so a future edit cannot tolerate a default-less field by
    accident.
    """

    class NoDefault(BaseModel):
        score: Annotated[int, WrapValidator(_use_default_for_unusable)]

    leaked = NoDefault.model_validate({"score": "unusable"}).score

    assert isinstance(leaked, PydanticUseDefault)


def test_salvage_refuses_a_tolerated_field_with_no_default() -> None:
    """The safe side of P11: `_salvage` re-raises rather than placing a marker."""

    class Required(BaseModel):
        count: int  # deliberately no default

    with pytest.raises(ValidationError) as excinfo:
        _salvage(Required, {})

    assert [error["type"] for error in excinfo.value.errors()] == ["missing"]


# --- the wiring: complete_structured actually uses the salvage path ------------


async def test_complete_structured_salvages_a_truncated_structured_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A truncated `info.structured` string degrades to a validated result.

    This is the test that distinguishes a wired salvage from a bare
    `model_validate`: the payload is not valid JSON, so without `_salvage` the
    call would classify as `invalid`.
    """
    body = dict(LIVE_MESSAGE_BODY)
    body["info"] = dict(body["info"])
    body["info"]["structured"] = '{"acknowledged": true, "echo": "ok", "extra": tru'
    recorder = Recorder(message_body=body)
    backend = _backend(monkeypatch, recorder)

    result = await backend.complete_structured(
        schema=ProbeResult, system="s", parts=["p"], retries=2
    )

    assert result.ok is True
    assert result.status == "ok"
    assert result.data == ProbeResult(acknowledged=True, echo="ok")


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
