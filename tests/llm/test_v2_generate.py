"""GEN-1 / TEL-1 — the V2 generate protocol completes end to end through the port.

The tracer test for phase 07.1. It proves, with **no socket opened**, the whole V2
happy path:

* detection reads the surface from `GET /api/info`'s JSON `version` (never from a
  200 alone — the SPA fallback serves HTML on every legacy path);
* the completion issues exactly `POST /api/session` then
  `POST /api/session/{id}/generate`;
* the session body's `model` is a `Model.Ref` OBJECT (`{id, providerID}`), never a
  bare string (a bare string is an HTTP 400 — Pitfall P1);
* the generated text at `data.text` is extracted, salvaged, and returned as a
  **typed** instance, with the session id read at `("data","id")` (Pitfall P2).

`httpx` is swapped for a recorder in every test here, so nothing touches the
network. `discover_models` is stubbed on the instance so the recorder observes
only the V2 requests (discovery is retargeted in plan 07.1-04).
"""

from __future__ import annotations

import json
import types
from typing import Any

import httpx
import pytest
import structlog

from app.config import settings
from app.domain.cv import TailoringPatch
from app.domain.schemas.probe import ProbeResult
from app.llm import opencode_server
from app.llm.base import DiscoveryResult, ProviderModel, StructuredCallResult
from app.llm.builders import GENERATE_SCHEMA_DIRECTIVE
from app.llm.contract import (
    GENERATE_PATH,
    INFO_PATH,
    MODEL_REF_FIELDS,
    V2_SESSION_PATH,
)
from app.llm.opencode_server import OpenCodeServerBackend

V2_SESSION_ID = "ses_v2test123"
V2_SERVER_VERSION = "2.0.26"
VALID_TEXT = json.dumps(
    {"acknowledged": True, "instruction_detected": True, "echo": "ok"}
)


class Recorder:
    """A fake `httpx` module for `app.llm.opencode_server`, recording requests.

    `requests` records the completion POSTs as `(method, url, json_body)` — the
    sequence the V2 protocol is asserted on. `paths` records the GET probes
    separately, so the detection probe never pollutes the POST-sequence assertion.
    """

    def __init__(
        self,
        *,
        info: tuple[int, Any, str] = (200, {"version": V2_SERVER_VERSION}, "application/json"),
        health: tuple[int, Any, str] = (200, {"healthy": True}, "application/json"),
        session: tuple[int, Any] = (200, {"data": {"id": V2_SESSION_ID}}),
        generate: tuple[int, Any] = (200, {"data": {"text": VALID_TEXT}}),
        generate_body: Any = None,
        generate_bodies: list[tuple[int, Any]] | None = None,
        error: BaseException | None = None,
        post_error: BaseException | None = None,
        generate_error: BaseException | None = None,
    ) -> None:
        self.requests: list[tuple[str, str, Any]] = []
        self.paths: list[str] = []
        self.client_kwargs: list[dict[str, Any]] = []
        self._info = info
        self._health = health
        self._session = session
        self._generate = generate
        self._generate_body = generate_body
        self._generate_bodies = generate_bodies
        self._generate_index = 0
        self._error = error
        self._post_error = post_error
        self._generate_error = generate_error

    def module(self) -> types.SimpleNamespace:
        recorder = self

        class FakeResponse:
            def __init__(
                self, status_code: int, body: Any, content_type: str = "application/json"
            ) -> None:
                self.status_code = status_code
                self._body = body
                self.headers = {"content-type": content_type}

            @property
            def text(self) -> str:
                return self._body if isinstance(self._body, str) else ""

            def json(self) -> Any:
                if isinstance(self._body, str):
                    return json.loads(self._body)
                return self._body

        class FakeClient:
            def __init__(self, **kwargs: Any) -> None:
                recorder.client_kwargs.append(kwargs)

            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *exc: object) -> bool:
                return False

            async def get(self, url: str) -> Any:
                recorder.paths.append(url)
                if recorder._error is not None:
                    raise recorder._error
                status, body, content_type = (
                    recorder._info if url == INFO_PATH else recorder._health
                )
                return FakeResponse(status, body, content_type)

            async def post(self, url: str, json: Any = None) -> Any:
                recorder.requests.append(("POST", url, json))
                if recorder._post_error is not None:
                    raise recorder._post_error
                if url == V2_SESSION_PATH:
                    return FakeResponse(recorder._session[0], recorder._session[1])
                if recorder._generate_error is not None:
                    raise recorder._generate_error
                if recorder._generate_bodies is not None:
                    # Per-call bodies: the nth generate POST gets the nth entry (the
                    # last is repeated once exhausted). Lets a test script a corrected
                    # second reply.
                    index = min(recorder._generate_index, len(recorder._generate_bodies) - 1)
                    recorder._generate_index += 1
                    status, body = recorder._generate_bodies[index]
                    return FakeResponse(status, body)
                body = (
                    recorder._generate_body
                    if recorder._generate_body is not None
                    else recorder._generate[1]
                )
                status = recorder._generate[0]
                return FakeResponse(status, body)

        # The module looks exception types up on the `httpx` name it imports.
        return types.SimpleNamespace(
            AsyncClient=FakeClient,
            BasicAuth=httpx.BasicAuth,
            TimeoutException=httpx.TimeoutException,
            TransportError=httpx.TransportError,
            ConnectTimeout=httpx.ConnectTimeout,
        )


def _v2_backend(
    monkeypatch: pytest.MonkeyPatch,
    recorder: Recorder,
    *,
    provider_id: str = "opencode-go",
    model_id: str | None = None,
    password: str = "test-server-password",
) -> OpenCodeServerBackend:
    """A backend whose discovery is stubbed; detection runs through the recorder.

    `model_id` resolves at CALL time, not at import: the hermetic fixture pins
    `settings.opencode_model` per test, so a default bound at collection would
    advertise a different model than the port then looks for.
    """
    if model_id is None:
        model_id = settings.opencode_model
    backend = OpenCodeServerBackend(password=password)

    async def _discover() -> DiscoveryResult:
        return DiscoveryResult(
            reachable=True,
            providers=[ProviderModel(provider_id=provider_id, model_id=model_id)],
        )

    monkeypatch.setattr(backend, "discover_models", _discover)
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())
    return backend


async def test_a_v2_generate_returns_a_validated_typed_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder()
    backend = _v2_backend(monkeypatch, recorder)

    result = await backend.complete_structured(
        schema=ProbeResult,
        system="a constant",
        parts=["untrusted"],
        retries=2,
    )

    assert isinstance(result, StructuredCallResult)
    assert result.ok is True
    assert result.status == "ok"
    assert result.data == ProbeResult(
        acknowledged=True, instruction_detected=True, echo="ok"
    )
    assert isinstance(result.data, ProbeResult)
    assert not isinstance(result.data, dict)


async def test_the_v2_protocol_makes_exactly_session_then_generate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder()
    backend = _v2_backend(monkeypatch, recorder)

    await backend.complete_structured(schema=ProbeResult, system="a constant", parts=["p"])

    assert [(method, url) for method, url, _ in recorder.requests] == [
        ("POST", V2_SESSION_PATH),
        ("POST", GENERATE_PATH.format(session_id=V2_SESSION_ID)),
    ]
    # Detection probed the V2 liveness path exactly once.
    assert recorder.paths == [INFO_PATH]


async def test_the_v2_session_body_carries_a_model_ref_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare-string `model` is an HTTP 400 — the shape must be the object."""
    recorder = Recorder()
    backend = _v2_backend(monkeypatch, recorder)

    await backend.complete_structured(schema=ProbeResult, system="s", parts=["p"])

    session_body = recorder.requests[0][2]
    assert set(session_body["model"]) == set(MODEL_REF_FIELDS)
    assert session_body["model"][MODEL_REF_FIELDS[0]] == settings.opencode_model
    assert session_body["model"][MODEL_REF_FIELDS[1]] == "opencode-go"


async def test_the_generate_body_carries_only_the_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder()
    backend = _v2_backend(monkeypatch, recorder)

    await backend.complete_structured(schema=ProbeResult, system="s", parts=["p"])

    generate_body = recorder.requests[1][2]
    assert set(generate_body) == {"prompt"}
    assert generate_body["prompt"]


async def test_a_spa_html_200_is_not_v1_and_not_reachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The SPA fallback returns 200 `text/html` on every legacy path (Pitfall P4)."""
    recorder = Recorder(
        info=(200, "<html>SPA</html>", "text/html"),
        health=(200, "<html>SPA</html>", "text/html"),
    )
    backend = _v2_backend(monkeypatch, recorder)

    outcome = await backend.health()

    assert outcome.reachable is False
    assert outcome.version is None


# --- GEN-3: the client-side schema-retry loop (D-139/D-140) --------------------

INVALID_TEXT = json.dumps({"acknowledged": "not-a-bool"})


def _first_validation_message() -> str:
    """The exact pydantic message the retry feeds back (D-140)."""
    try:
        ProbeResult(acknowledged="not-a-bool")  # type: ignore[arg-type]
    except ValueError as exc:  # noqa: BLE001 — ValidationError is a ValueError
        errors = getattr(exc, "errors", lambda: [])()
        assert errors, "the control input must actually fail validation"
        return errors[0]["msg"]
    raise AssertionError("the control input unexpectedly validated")


def _generate_requests(recorder: Recorder) -> list[tuple[str, str, Any]]:
    return [entry for entry in recorder.requests if entry[1].endswith("/generate")]


async def test_the_schema_retry_loop_issues_one_plus_the_configured_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder(generate=(200, {"data": {"text": INVALID_TEXT}}))
    backend = _v2_backend(monkeypatch, recorder)

    result = await backend.complete_structured(
        schema=ProbeResult, system="s", parts=["p"]
    )

    expected = 1 + settings.opencode_structured_retry_count
    generates = _generate_requests(recorder)
    assert len(generates) == expected
    assert result.ok is False
    assert result.status == "invalid"
    assert result.error_kind == "invalid"
    assert result.attempts == expected


async def test_the_reissued_prompt_carries_the_first_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder(generate=(200, {"data": {"text": INVALID_TEXT}}))
    backend = _v2_backend(monkeypatch, recorder)

    await backend.complete_structured(schema=ProbeResult, system="s", parts=["p"])

    messages = [entry[2]["prompt"] for entry in _generate_requests(recorder)]
    first_validation_message = _first_validation_message()
    # The initial prompt carries no feedback; every retry does.
    assert first_validation_message not in messages[0]
    for prompt in messages[1:]:
        assert first_validation_message in prompt


DUPLICATE_TARGET_TEXT = json.dumps(
    {
        "listing_id": 183,
        "ops": [
            {"op": "reweight_bullet", "bullet_id": "bul/devdesk-2026/2", "weight": 1.0},
            {"op": "move_bullet", "bullet_id": "bul/devdesk-2026/2"},
        ],
    }
)
CORRECTED_TEXT = json.dumps({"listing_id": 183, "ops": []})


async def test_a_duplicate_target_patch_is_retried_inside_the_schema_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The live 502 repro: a duplicate-target patch spends the schema budget.

    `TailoringPatch`'s schema validator raises the `ValidationError` inside `_salvage`,
    so the loop feeds the offending id back and re-issues `generate` — attempts 2,
    not the single shot that escaped to `InvalidPatchError` before.
    """
    recorder = Recorder(
        generate_bodies=[
            (200, {"data": {"text": DUPLICATE_TARGET_TEXT}}),
            (200, {"data": {"text": CORRECTED_TEXT}}),
        ]
    )
    backend = _v2_backend(monkeypatch, recorder)

    result = await backend.complete_structured(schema=TailoringPatch, system="s", parts=["p"])

    generates = _generate_requests(recorder)
    assert len(generates) == 2, "the first reply is retried, not one-shot refused"
    assert result.ok is True
    assert result.attempts == 2
    assert isinstance(result.data, TailoringPatch)
    # The re-issued prompt carries the offending id the validator named.
    assert "bul/devdesk-2026/2" not in generates[0][2]["prompt"]
    assert "bul/devdesk-2026/2" in generates[1][2]["prompt"]


# --- CR-01: the transport-retry loop runs on V2 too (D-151) --------------------


@pytest.mark.parametrize("budget", [1, 2, 3])
async def test_a_v2_transport_failure_is_retried_bounded_by_retries(
    monkeypatch: pytest.MonkeyPatch, budget: int
) -> None:
    """CR-01: `OPENCODE_MAX_RETRIES` governs the V2 arm too, and `attempts` is honest.

    Before the transport loop, a single `ConnectError` on `/api/session` escaped to
    the outer envelope and returned `attempts=0` with exactly ONE POST issued, so
    the configured retry budget was inert. The repro class is "all completion POSTs
    raise at the transport layer"; the budget must bound the resends and `attempts`
    must report the issued count — the V1 arm's behaviour, now mirrored.
    """
    recorder = Recorder(post_error=httpx.ConnectError("connection refused"))
    backend = _v2_backend(monkeypatch, recorder)

    result = await backend.complete_structured(
        schema=ProbeResult, system="s", parts=["p"], retries=budget
    )

    assert result.ok is False
    assert result.status == "error"
    assert result.error_kind == "unreachable"
    assert len(recorder.requests) == budget
    assert result.attempts == budget


async def test_an_omitted_retries_honours_the_settings_ceiling_on_v2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An omitted `retries` is bounded by `opencode_max_retries` on V2 as on V1."""
    monkeypatch.setattr(settings, "opencode_max_retries", 3)
    recorder = Recorder(post_error=httpx.ConnectError("connection refused"))
    backend = _v2_backend(monkeypatch, recorder)

    result = await backend.complete_structured(schema=ProbeResult, system="s", parts=["p"])

    assert len(recorder.requests) == 3
    assert result.attempts == 3
    assert result.error_kind == "unreachable"


async def test_a_v2_generate_transport_failure_is_retried_after_a_good_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The session succeeds once; each `generate` POST resends to the transport budget."""
    recorder = Recorder(generate_error=httpx.ReadTimeout("slow response"))
    backend = _v2_backend(monkeypatch, recorder)

    result = await backend.complete_structured(
        schema=ProbeResult, system="s", parts=["p"], retries=2
    )

    assert len(_generate_requests(recorder)) == 2
    assert result.status == "timeout"
    assert result.error_kind == "timeout"
    assert result.attempts == 2


# --- AUTH: auth is opt-in; 401 is `unauthenticated` (D-136/D-137) --------------


async def test_an_empty_password_reaches_an_unsecured_server_with_no_auth_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unsecured (default) server works with no configured password (D-136).

    Auth is opt-in upstream: with no password the client sends no `Authorization`
    header and the server serves `/api/*` unauthenticated. The repro class is
    "empty password + a healthy server"; the completion must succeed, not fail
    fast, and the client must be built with `auth=None`.
    """
    recorder = Recorder()
    backend = _v2_backend(monkeypatch, recorder, password="")

    result = await backend.complete_structured(
        schema=ProbeResult, system="s", parts=["p"]
    )

    assert result.ok is True
    assert result.status == "ok"
    assert result.attempts == 1
    # A request was actually issued, and no client carried an auth header.
    assert [(method, url) for method, url, _ in recorder.requests] == [
        ("POST", V2_SESSION_PATH),
        ("POST", GENERATE_PATH.format(session_id=V2_SESSION_ID)),
    ]
    assert recorder.client_kwargs and all(
        kwargs["auth"] is None for kwargs in recorder.client_kwargs
    )


async def test_an_empty_password_against_a_secured_server_is_unauthenticated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A password-protected server reached with no password is `unauthenticated`.

    The distinct cause survives the opt-in model: the client sends no header, the
    secured server answers `401`, and that is classified `unauthenticated` rather
    than a bare `http_401`.
    """
    recorder = Recorder(
        session=(401, {"_tag": "UnauthorizedError", "message": "Authentication required"})
    )
    backend = _v2_backend(monkeypatch, recorder, password="")

    result = await backend.complete_structured(
        schema=ProbeResult, system="s", parts=["p"]
    )

    assert result.ok is False
    assert result.status == "error"
    assert result.error_kind == "unauthenticated"


async def test_a_session_401_is_unauthenticated_not_a_generic_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder(
        session=(401, {"_tag": "UnauthorizedError", "message": "Authentication required"})
    )
    backend = _v2_backend(monkeypatch, recorder)

    result = await backend.complete_structured(
        schema=ProbeResult, system="s", parts=["p"]
    )

    assert result.status == "error"
    assert result.error_kind == "unauthenticated"


async def test_a_generate_401_is_unauthenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = Recorder(
        generate=(401, {"_tag": "UnauthorizedError", "message": "Authentication required"})
    )
    backend = _v2_backend(monkeypatch, recorder)

    result = await backend.complete_structured(
        schema=ProbeResult, system="s", parts=["p"]
    )

    assert result.status == "error"
    assert result.error_kind == "unauthenticated"
    assert result.attempts == 1


# --- TEL-1: the V2 telemetry semantics (D-143/D-144) ---------------------------


async def test_a_v2_result_records_the_configured_model_and_no_served_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder()
    backend = _v2_backend(monkeypatch, recorder)

    result = await backend.complete_structured(
        schema=ProbeResult, system="s", parts=["p"]
    )

    assert result.ok is True
    assert result.model == settings.opencode_model
    assert result.provider is None
    assert result.agent is None
    assert result.provider_tokens is None
    assert isinstance(result.server_version, str) and result.server_version


# --- FIX 2: a failed V2 completion emits exactly one structured warning --------


def _v2_failure_warnings(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event.get("event") == "llm.v2_completion_failed"]


async def test_a_failed_v2_completion_emits_one_structured_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cause must survive without the `llm_calls` `error_kind` column.

    The recorded live failure was undiagnosable because the V2 arm logged nothing
    and only `status` persisted. One bounded warning now carries the discriminator.
    """
    recorder = Recorder(generate=(200, {"data": {"text": INVALID_TEXT}}))
    backend = _v2_backend(monkeypatch, recorder)

    with structlog.testing.capture_logs() as events:
        result = await backend.complete_structured(
            schema=ProbeResult, system="s", parts=["p"]
        )

    assert result.ok is False
    warnings = _v2_failure_warnings(events)
    assert len(warnings) == 1, "exactly one warning per failed call"
    assert warnings[0]["backend"] == "opencode_server"
    assert warnings[0]["status"] == "invalid"
    assert warnings[0]["error_kind"] == "invalid"
    assert warnings[0]["attempts"] == result.attempts
    assert warnings[0]["provider"] == "opencode-go"
    assert warnings[0]["model"] == settings.opencode_model
    assert warnings[0]["server_version"] == V2_SERVER_VERSION


async def test_the_warning_carries_the_http_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An HTTP failure is attributed by `error_kind` (`http_<code>`)."""
    recorder = Recorder(session=(500, {"error": "boom"}))
    backend = _v2_backend(monkeypatch, recorder)

    with structlog.testing.capture_logs() as events:
        result = await backend.complete_structured(
            schema=ProbeResult, system="s", parts=["p"]
        )

    assert result.ok is False
    warnings = _v2_failure_warnings(events)
    assert len(warnings) == 1
    assert warnings[0]["status"] == "error"
    assert warnings[0]["error_kind"] == "http_500"


async def test_a_successful_v2_completion_emits_no_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder()
    backend = _v2_backend(monkeypatch, recorder)

    with structlog.testing.capture_logs() as events:
        result = await backend.complete_structured(
            schema=ProbeResult, system="s", parts=["p"]
        )

    assert result.ok is True
    assert _v2_failure_warnings(events) == []


# --- the live repro: an unattributable `attempts=1` `status=invalid` -----------
#
# The recorded failure — for BOTH tailoring and drafting:
#
#   2026-10-14 10:12:09 [warning] llm.v2_completion_failed attempts=1
#   backend=opencode_server error_kind=invalid model=big-pickle provider=opencode
#   server_version=2.0.26 status=invalid
#
# `attempts=1` proves the schema-retry loop never retried, so it exited via one of
# the two early returns below. Both are now observable and (for the JSON case)
# retried to the same budget.

#: Plain prose with no brace at all, so `_extract_json` returns it unchanged and
#: `_salvage`'s `from_json` raises a bare `ValueError` (not a `ValidationError`).
NON_JSON_TEXT = "the model answered in prose with no json object"


@pytest.mark.parametrize(
    "part_types, parts_body",
    [
        (["reasoning"], [{"type": "reasoning", "text": "LEAK-REASONING"}]),
        (
            ["reasoning", "text"],
            [
                {"type": "reasoning", "text": "LEAK-A"},
                {"type": "text", "text": "LEAK-B"},
            ],
        ),
        (["step-start"], [{"type": "step-start", "text": "LEAK-C"}]),
        (["unknown"], [{"text": "no type field"}]),
    ],
)
async def test_a_parts_only_reply_names_the_part_types_and_never_their_text(
    monkeypatch: pytest.MonkeyPatch,
    part_types: list[str],
    parts_body: list[dict[str, Any]],
) -> None:
    """`no text` + parts is told apart from `no text` + nothing, without leaking text.

    Failure class: a `generate` 200 whose `data.text` is absent but whose parts
    carry content. The cause must name the part TYPES; a secret planted in a part's
    `text` must never reach `error`.
    """
    recorder = Recorder(generate=(200, {"data": {}, "parts": parts_body}))
    backend = _v2_backend(monkeypatch, recorder)

    result = await backend.complete_structured(
        schema=ProbeResult, system="s", parts=["p"]
    )

    assert result.ok is False
    assert result.status == "invalid"
    assert result.attempts == 1
    error = result.error or ""
    assert "generate response carried no text" in error
    for expected in part_types:
        assert expected in error
    assert "LEAK" not in error, "a part's text must never reach the error"
    assert result.part_types == part_types


async def test_a_no_text_no_parts_reply_is_distinguished_from_a_parts_only_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`parts: None` names the other half of the same class — no parts observed."""
    recorder = Recorder(generate=(200, {"data": {}}))
    backend = _v2_backend(monkeypatch, recorder)

    result = await backend.complete_structured(
        schema=ProbeResult, system="s", parts=["p"]
    )

    assert result.status == "invalid"
    assert "carried no text" in (result.error or "")
    assert "parts: None" in (result.error or "")
    assert result.part_types is None


@pytest.mark.parametrize("retries", [1, 2, 3])
async def test_a_non_json_generate_consumes_the_full_schema_budget(
    monkeypatch: pytest.MonkeyPatch, retries: int
) -> None:
    """The JSON-parse failure retries like a validation failure (D-140 parity).

    Before the fix a single non-JSON `generate` returned immediately — `attempts=1`
    with `status=invalid`, the exact live symptom. It must now spend the whole
    schema budget (`1 + opencode_structured_retry_count`) and feed the cause back.
    """
    monkeypatch.setattr(settings, "opencode_structured_retry_count", retries)
    recorder = Recorder(generate=(200, {"data": {"text": NON_JSON_TEXT}}))
    backend = _v2_backend(monkeypatch, recorder)

    result = await backend.complete_structured(
        schema=ProbeResult, system="s", parts=["p"]
    )

    expected = 1 + retries
    messages = [entry[2]["prompt"] for entry in _generate_requests(recorder)]
    assert len(messages) == expected
    assert result.ok is False
    assert result.status == "invalid"
    assert result.error_kind == "invalid"
    assert result.attempts == expected
    assert "not valid JSON" in (result.error or "")
    # The initial prompt carries no feedback; every retry names the JSON defect.
    assert "not valid JSON" not in messages[0]
    for prompt in messages[1:]:
        assert "not valid JSON" in prompt


@pytest.mark.parametrize(
    "generate_text, expected, forbidden",
    [
        (NON_JSON_TEXT, "generated text was not valid JSON", "validation failed"),
        (INVALID_TEXT, "validation failed", "not valid JSON"),
    ],
)
async def test_the_final_message_distinguishes_json_parse_from_schema_validation(
    monkeypatch: pytest.MonkeyPatch,
    generate_text: str,
    expected: str,
    forbidden: str,
) -> None:
    """The exhausted-budget exit must say WHICH kind of invalid it was."""
    recorder = Recorder(generate=(200, {"data": {"text": generate_text}}))
    backend = _v2_backend(monkeypatch, recorder)

    result = await backend.complete_structured(
        schema=ProbeResult, system="s", parts=["p"]
    )

    assert result.status == "invalid"
    assert expected in (result.error or "")
    assert forbidden not in (result.error or "")


@pytest.mark.parametrize(
    "generate_body",
    [
        {"data": {}, "parts": [{"type": "reasoning", "text": "LEAK-WARNING"}]},
        {"data": {"text": NON_JSON_TEXT}},
    ],
)
async def test_the_failure_warning_carries_the_bounded_error(
    monkeypatch: pytest.MonkeyPatch, generate_body: dict[str, Any]
) -> None:
    """`error` is added to the one warning so the cause is in the log itself.

    Only bounded strings reach it (a pydantic `msg`, a `JSONDecodeError` message or
    `_bounded_excerpt`); a secret planted in a part's text must not.
    """
    recorder = Recorder(generate=(200, generate_body))
    backend = _v2_backend(monkeypatch, recorder)

    with structlog.testing.capture_logs() as events:
        result = await backend.complete_structured(
            schema=ProbeResult, system="s", parts=["p"]
        )

    assert result.ok is False
    warnings = _v2_failure_warnings(events)
    assert len(warnings) == 1
    assert warnings[0]["error"] == result.error
    assert isinstance(warnings[0]["error"], str) and warnings[0]["error"]
    assert "LEAK" not in warnings[0]["error"]


def test_the_generate_directive_forbids_prose_and_code_fences() -> None:
    """The schema directive asks for the bare object, and the schema keeps its slot.

    `INVALID_TEXT` observed live was a fenced/prose-wrapped reply, so the directive
    now says so explicitly. The order (system → directive + schema → untrusted
    delimiter) is unchanged.
    """
    assert "nothing else" in GENERATE_SCHEMA_DIRECTIVE
    assert "no prose" in GENERATE_SCHEMA_DIRECTIVE
    assert "markdown code fences" in GENERATE_SCHEMA_DIRECTIVE

    prompt = opencode_server.to_generate_prompt(
        schema=ProbeResult, system="SENTINEL-SYSTEM", parts=["P"]
    )
    assert (
        prompt.index("SENTINEL-SYSTEM")
        < prompt.index(GENERATE_SCHEMA_DIRECTIVE)
        < prompt.index('"acknowledged"')
        < prompt.index("untrusted data")
    )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])

