"""The LLM backend port — Phase 1 scope: health and discovery only.

Phase 1 makes **no** LLM call. What ships here is the seam Phase 3 extends:
`health()` exposes the server version and `discover_models()` exposes model ids, so
D-12's per-call model+version recording can be added without changing this
interface or any route signature.

**Redaction is a type-level property (D-11).** `GET /config/providers` returns the
provider API key in plaintext. `ProviderModel` therefore carries exactly two
fields and forbids extras, so a raw payload, a key, or a free-form raw dict is
*unrepresentable* rather than merely unused (Pitfall 11).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ProviderModel(BaseModel):
    """One available model, identified only.

    `extra="forbid"` is the redaction control: feeding a raw provider entry (which
    carries `api_key`) to this type raises rather than silently dropping the
    secret, so the mistake is loud and the credential never lands on an attribute.
    """

    model_config = ConfigDict(extra="forbid")

    provider_id: str
    model_id: str


class DiscoveryResult(BaseModel):
    """The redacted discovery outcome: identifiers only, never the response."""

    providers: list[ProviderModel] = Field(default_factory=list)
    reachable: bool
    version: str | None = None
    error: str | None = None


class ProbeOutcome(BaseModel):
    """A non-raising reachability result. Health probes never raise (D-08)."""

    reachable: bool
    version: str | None = None
    error: str | None = None


@runtime_checkable
class LLMBackend(Protocol):
    """The ONLY surface the app depends on. Phase 3 adds `complete_structured`."""

    async def health(self) -> ProbeOutcome:
        """Server reachability (and version when reported). Never raises."""
        ...

    async def discover_models(self) -> DiscoveryResult:
        """Available provider/model ids. Never raises; never returns the body."""
        ...


__all__ = ["DiscoveryResult", "LLMBackend", "ProbeOutcome", "ProviderModel"]
