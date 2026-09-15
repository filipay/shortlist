"""The opencode HTTP backend — health (D-08), discovery (D-09), redaction (D-11).

Two endpoints, both narrow:

* ``GET /global/health`` — reachability, and the version when the server reports
  one. A failure is `reachable=False`, never an exception: `docker compose up`
  must not depend on an LLM backend being up (D-08).
* ``GET /config/providers`` — the subscription-scoped provider/model set the user
  actually configured. The full vendor catalogue endpoint (``/provider``, ~6 MB,
  217 providers) is deliberately **not** referenced anywhere in this module (D-09);
  `tests/llm/test_discovery_redaction.py` asserts both the behaviour and the
  absence of that path.

The discovery response carries the provider API key in plaintext, so it is parsed
straight into identifiers and never logged, never stored on an attribute, never
cached and never returned (D-11 / T-01-29).
"""

from __future__ import annotations

import httpx
import structlog

from app.config import settings
from app.llm.base import DiscoveryResult, ProbeOutcome, ProviderModel

log = structlog.get_logger(__name__)

GLOBAL_HEALTH_PATH = "/global/health"
CONFIG_PROVIDERS_PATH = "/config/providers"


def parse_providers(payload: object) -> list[ProviderModel]:
    """Extract `(provider_id, model_id)` pairs from a discovery payload.

    Tolerant by design (Assumptions Log A2: the live response shape was never read
    during research). A payload that is not a mapping, a provider with no `models`
    list, a model with no `id`, and a non-mapping entry each contribute nothing —
    the parse fails to an empty list rather than raising, and the caller gets a
    deterministic result either way.

    Only the two identifiers are copied. Provider-level extras (notably
    `api_key`) are read past, never assigned.
    """
    if not isinstance(payload, dict):
        return []

    entries = payload.get("providers")
    if not isinstance(entries, list):
        return []

    found: list[ProviderModel] = []
    for provider in entries:
        if not isinstance(provider, dict):
            continue
        provider_id = provider.get("id")
        if not isinstance(provider_id, str) or not provider_id:
            continue
        models = provider.get("models")
        if not isinstance(models, list):
            continue
        for model in models:
            if not isinstance(model, dict):
                continue
            model_id = model.get("id")
            if not isinstance(model_id, str) or not model_id:
                continue
            found.append(ProviderModel(provider_id=provider_id, model_id=model_id))

    return sorted(found, key=lambda entry: (entry.provider_id, entry.model_id))


class OpenCodeServerBackend:
    """Reachability and discovery over HTTP. Phase 1 makes no LLM call."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        password: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self._base_url = base_url if base_url is not None else settings.opencode_base_url
        self._password = (
            password if password is not None else settings.opencode_server_password
        )
        self._timeout = (
            timeout if timeout is not None else settings.opencode_timeout_seconds
        )

    def _auth(self) -> httpx.BasicAuth | None:
        """Basic auth only when a password is configured (D-07).

        An empty password means "send no auth header at all", not "send blanks".
        The value comes from configuration, never from a literal.
        """
        if not self._password:
            return None
        return httpx.BasicAuth("opencode", self._password)

    def _client(self) -> httpx.AsyncClient:
        """A bounded client (T-01-32: a hung call must not pin the single worker)."""
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            auth=self._auth(),
        )

    async def health(self) -> ProbeOutcome:
        """`GET /global/health`. `reachable=False` on any failure (D-08)."""
        try:
            async with self._client() as client:
                response = await client.get(GLOBAL_HEALTH_PATH)
        except Exception as exc:  # noqa: BLE001 — boot tolerance
            return ProbeOutcome(reachable=False, error=type(exc).__name__)

        if response.status_code != 200:
            return ProbeOutcome(reachable=False, error=f"HTTP {response.status_code}")

        try:
            body = response.json()
        except Exception:  # noqa: BLE001 — a non-JSON 200 still means reachable
            return ProbeOutcome(reachable=True)

        version = body.get("version") if isinstance(body, dict) else None
        return ProbeOutcome(
            reachable=True,
            version=version if isinstance(version, str) else None,
        )

    async def discover_models(self) -> DiscoveryResult:
        """`GET /config/providers`, parsed straight into identifiers (D-09/D-11)."""
        try:
            async with self._client() as client:
                response = await client.get(CONFIG_PROVIDERS_PATH)
                if response.status_code != 200:
                    return DiscoveryResult(
                        reachable=False,
                        error=f"discovery returned HTTP {response.status_code}",
                    )
                # The body carries a plaintext provider credential. It is consumed
                # as an argument to the parse and never assigned to an attribute,
                # never logged, never cached to disk and never returned; only the
                # identifiers extracted by `parse_providers` leave this block.
                providers = parse_providers(response.json())
        except Exception as exc:  # noqa: BLE001 — discovery is total
            return DiscoveryResult(reachable=False, error=type(exc).__name__)

        log.info(
            "llm.discovery",
            backend="opencode_server",
            provider_count=len({entry.provider_id for entry in providers}),
            model_count=len(providers),
        )
        return DiscoveryResult(providers=providers, reachable=True)


__all__ = [
    "CONFIG_PROVIDERS_PATH",
    "GLOBAL_HEALTH_PATH",
    "OpenCodeServerBackend",
    "parse_providers",
]
