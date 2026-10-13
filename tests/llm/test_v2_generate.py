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
