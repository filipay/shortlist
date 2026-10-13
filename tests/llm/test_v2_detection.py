"""DET-1 / DET-2 — dual-surface detection, and the SPA-200 false positive fixed.

opencode 2.0.26 serves the web-UI SPA (HTTP 200 `text/html`) on every legacy root
path, so `health()` used to report `reachable=True` with no version against a
broken backend. These tests pin the retarget:

* the pure classifier (`classify_surface`) requires a JSON OBJECT body — an HTML
  content type, a non-200, or a non-object body is `unknown`;
* `detect_surface` probes `/api/info` (V2) then `/global/health` (V1);
* a process-local cache serves a known verdict but NEVER caches `unknown`.

No socket is opened — the default lane is offline by construction.
"""

from __future__ import annotations

import json
import types
from typing import Any

import httpx
import pytest

from app.config import settings
from app.llm import opencode_server
from app.llm.contract import GLOBAL_HEALTH_PATH, INFO_PATH
from app.llm.detection import (
    classify_surface,
    clear_cache,
    detect_surface,
)
from app.llm.opencode_server import OpenCodeServerBackend

BASE_URL = "http://opencode.test:4096"


class FakeResponse:
    def __init__(self, status_code: int, body: Any, content_type: str) -> None:
        self.status_code = status_code
        self._body = body
        self.headers = {"content-type": content_type}

    def json(self) -> Any:
        if isinstance(self._body, str):
            # A real HTML body is not JSON — mirror that so the probe's tolerance
            # path is exercised, not a pre-decoded string.
            return json.loads(self._body)
        return self._body


class ProbeRecorder:
    """A per-path fake for the detection probes; records every GET."""

    def __init__(
        self,
        *,
        responses: dict[str, tuple[int, Any, str]] | None = None,
        default: tuple[int, Any, str] = (200, {"healthy": True}, "application/json"),
    ) -> None:
        self.paths: list[str] = []
        self.responses = dict(responses or {})
        self.default = default

    def _response(self, url: str) -> FakeResponse:
        status, body, content_type = self.responses.get(url, self.default)
        return FakeResponse(status, body, content_type)

    def client(self) -> Any:
        recorder = self

        class Client:
            async def get(self, url: str) -> FakeResponse:
                recorder.paths.append(url)
                return recorder._response(url)

            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *exc: object) -> bool:
                return False

        return Client()

    def module(self) -> types.SimpleNamespace:
        recorder = self

        class Client:
            def __init__(self, **kwargs: Any) -> None:
                pass

            async def get(self, url: str) -> FakeResponse:
                recorder.paths.append(url)
                return recorder._response(url)

            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *exc: object) -> bool:
                return False

        return types.SimpleNamespace(
            AsyncClient=Client,
            BasicAuth=httpx.BasicAuth,
            TimeoutException=httpx.TimeoutException,
            TransportError=httpx.TransportError,
            ConnectTimeout=httpx.ConnectTimeout,
        )


# --- the pure classifier ------------------------------------------------------


@pytest.mark.parametrize(
    ("status_code", "content_type", "body", "expected"),
    [
        (200, "application/json", {"version": "2.0.26"}, "v2"),
        (200, "application/json", {"healthy": True}, "v1"),
        # A V1 health body carries BOTH markers — `healthy` must win.
        (200, "application/json", {"healthy": True, "version": "1.18.31"}, "v1"),
        (200, "text/html", "<html>SPA</html>", "unknown"),
        (200, "application/json", [1, 2, 3], "unknown"),
        (200, "application/json", "just a string", "unknown"),
        (200, "application/json", 7, "unknown"),
        (503, "application/json", {"version": "2.0.26"}, "unknown"),
        (200, "application/json", {}, "unknown"),
    ],
)
def test_classify_surface_cases(
    status_code: int, content_type: str, body: object, expected: str
) -> None:
    assert (
        classify_surface(
            status_code=status_code, content_type=content_type, body=body
        )
        == expected
    )


def test_classify_surface_rejects_the_spa_fallback_literal() -> None:
    """The exact DET-2 assertion: a 200 `text/html` body is never V1."""
    assert (
        classify_surface(status_code=200, content_type="text/html", body="<html>")
        == "unknown"
    )


# --- the async probe ----------------------------------------------------------


async def test_detect_surface_returns_v2_for_api_info_with_version() -> None:
    recorder = ProbeRecorder(
        responses={INFO_PATH: (200, {"version": "2.0.26"}, "application/json")}
    )

    probe = await detect_surface(base_url=BASE_URL, client=recorder.client())

    assert probe.surface == "v2"
    assert probe.version == "2.0.26"
    assert recorder.paths == [INFO_PATH]


async def test_detect_surface_falls_back_to_v1_when_api_info_is_html() -> None:
    recorder = ProbeRecorder(
        responses={
            INFO_PATH: (200, "<html>SPA</html>", "text/html"),
            GLOBAL_HEALTH_PATH: (
                200,
                json.dumps({"healthy": True, "version": "1.18.31"}),
                "application/json",
            ),
        }
    )

    probe = await detect_surface(base_url=BASE_URL, client=recorder.client())

    assert probe.surface == "v1"
    assert probe.version == "1.18.31"
    assert recorder.paths == [INFO_PATH, GLOBAL_HEALTH_PATH]


async def test_detect_surface_returns_unknown_when_both_are_spa_html() -> None:
    recorder = ProbeRecorder(default=(200, "<html>SPA</html>", "text/html"))

    probe = await detect_surface(base_url=BASE_URL, client=recorder.client())

    assert probe.surface == "unknown"
    assert recorder.paths == [INFO_PATH, GLOBAL_HEALTH_PATH]


async def test_health_is_not_reachable_on_spa_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DET-2 through the port: SPA HTML on both paths is NOT `reachable=True`."""
    recorder = ProbeRecorder(default=(200, "<html>SPA</html>", "text/html"))
    monkeypatch.setattr(opencode_server, "httpx", recorder.module())

    outcome = await OpenCodeServerBackend().health()

    assert outcome.reachable is False
    assert outcome.version is None


# --- the cache ----------------------------------------------------------------


async def test_detect_surface_caches_a_known_verdict() -> None:
    recorder = ProbeRecorder(
        responses={INFO_PATH: (200, {"version": "2.0.26"}, "application/json")}
    )
    client = recorder.client()

    first = await detect_surface(base_url=BASE_URL, client=client)
    second = await detect_surface(base_url=BASE_URL, client=client)

    assert first == second
    # A cached verdict is served without re-probing.
    assert recorder.paths == [INFO_PATH]


async def test_detect_surface_does_not_cache_unknown() -> None:
    """A server that starts later must become detectable (RESEARCH A2)."""
    recorder = ProbeRecorder(default=(200, "<html>SPA</html>", "text/html"))
    client = recorder.client()

    await detect_surface(base_url=BASE_URL, client=client)
    await detect_surface(base_url=BASE_URL, client=client)

    assert recorder.paths == [
        INFO_PATH,
        GLOBAL_HEALTH_PATH,
        INFO_PATH,
        GLOBAL_HEALTH_PATH,
    ]


async def test_clear_cache_forces_a_reprobe() -> None:
    recorder = ProbeRecorder(
        responses={INFO_PATH: (200, {"version": "2.0.26"}, "application/json")}
    )
    client = recorder.client()

    await detect_surface(base_url=BASE_URL, client=client)
    clear_cache()
    await detect_surface(base_url=BASE_URL, client=client)

    assert recorder.paths == [INFO_PATH, INFO_PATH]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
