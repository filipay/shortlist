"""Detect which opencode HTTP API surface a server exposes (D-147).

V1 (`/global/health`, `/session/…/message`) and V2 (`/api/info`,
`/api/session/…/generate`) are both supported; this module decides which one the
configured server speaks so `OpenCodeServerBackend` can dispatch to the matching
contract.

**Never classify from a bare HTTP 200.** opencode 2.0.26 serves the web-UI SPA
(HTTP 200 `text/html`) on every legacy root path, so a status code alone is a
false positive (Pitfall P4). A surface is recognised only from a 200 whose body
is a JSON OBJECT carrying the surface's marker key.

The probe reuses the caller's authenticated client, so `_auth()` stays the single
`httpx.BasicAuth` construction site (RESEARCH "Don't Hand-Roll") — this module
builds no auth of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx

from app.llm.contract import (
    GLOBAL_HEALTH_PATH,
    HEALTH_HEALTHY_FIELD,
    INFO_PATH,
    SERVER_INFO_VERSION_FIELD,
)

#: The detected API surface. `unknown` is never a success: it means neither probe
#: produced a recognisable JSON body, so the caller must fail closed.
Surface = Literal["v1", "v2", "unknown"]


@dataclass(frozen=True)
class SurfaceProbe:
    """The outcome of a surface probe — a value, never an exception."""

    surface: Surface
    version: str | None
    error: str | None


def _content_type(response: object) -> str | None:
    """The response's `content-type` header, or None when absent/unreadable.

    `getattr`-guarded so a minimal/partial response object (and the test
    recorders) cannot make the probe raise.
    """
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    try:
        value = headers.get("content-type")
    except Exception:  # noqa: BLE001 — a header is optional, never fatal
        return None
    return value if isinstance(value, str) else None


def classify_surface(
    *, status_code: int, content_type: str | None, body: object
) -> Surface:
    """Pure classifier: V2 / V1 / unknown from one probe response.

    Requires HTTP 200 AND a JSON OBJECT body (an HTML content type is a veto):
    * a body carrying `version` ⇒ V2;
    * a body carrying `healthy` ⇒ V1;
    * anything else ⇒ unknown.
    """
    if status_code != 200:
        return "unknown"
    if isinstance(content_type, str) and "html" in content_type.lower():
        return "unknown"
    if not isinstance(body, dict):
        return "unknown"
    if SERVER_INFO_VERSION_FIELD in body:
        return "v2"
    if HEALTH_HEALTHY_FIELD in body:
        return "v1"
    return "unknown"


def _version(body: object) -> str | None:
    """The `version` string on a probe body, or None when absent/unusable."""
    if not isinstance(body, dict):
        return None
    value = body.get(SERVER_INFO_VERSION_FIELD)
    return value if isinstance(value, str) and value else None


async def detect_surface(
    *, base_url: str, client: httpx.AsyncClient
) -> SurfaceProbe:
    """Probe V2 (`/api/info`) first, then V1 (`/global/health`); else unknown.

    V2-first because it is the installed server's surface and its JSON carries
    `version`. Total: a transport error or a non-JSON/HTML 200 yields `unknown`,
    never an exception. `base_url` identifies the probed server (the caller may
    cache on it).
    """
    last_error: str | None = None
    for path in (INFO_PATH, GLOBAL_HEALTH_PATH):
        try:
            response = await client.get(path)
        except Exception as exc:  # noqa: BLE001 — the probe is a total function
            last_error = type(exc).__name__
            continue
        status = getattr(response, "status_code", None)
        if status != 200:
            last_error = f"HTTP {status}"
            continue
        try:
            body = response.json()
        except Exception:  # noqa: BLE001 — the SPA serves HTML on these paths
            body = None
        surface = classify_surface(
            status_code=status, content_type=_content_type(response), body=body
        )
        if surface != "unknown":
            return SurfaceProbe(surface=surface, version=_version(body), error=None)
    return SurfaceProbe(surface="unknown", version=None, error=last_error)


__all__ = ["Surface", "SurfaceProbe", "classify_surface", "detect_surface"]
