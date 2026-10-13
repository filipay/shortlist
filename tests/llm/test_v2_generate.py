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

from app.config import settings
from app.domain.schemas.probe import ProbeResult
from app.llm import opencode_server
from app.llm.base import DiscoveryResult, ProviderModel, StructuredCallResult
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
    model_id: str = settings.opencode_model,
) -> OpenCodeServerBackend:
    """A backend whose discovery is stubbed; detection runs through the recorder."""
    backend = OpenCodeServerBackend(password="test-server-password")

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


# --- AUTH: empty password fails fast; 401 is `unauthenticated` (D-136/D-137) ----


async def test_an_empty_password_fails_fast_with_no_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = Recorder()
    backend = OpenCodeServerBackend(password="")
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

    result = await backend.complete_structured(
        schema=ProbeResult, system="s", parts=["p"]
    )

    assert result.ok is False
    assert result.status == "error"
    assert result.error_kind == "unauthenticated"
    assert result.attempts == 0
    # Not even the detection probe is issued.
    assert recorder.requests == []
    assert recorder.paths == []


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


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])

