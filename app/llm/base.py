"""The LLM backend port — health, discovery, and one structured completion.

Phase 1 shipped `health()` and `discover_models()`. Phase 3 adds
`complete_structured`: one schema-constrained call whose validated payload is
returned as a typed instance, never a raw dict. Validation is a **boundary
concern** (§6.2) — the domain never sees an unvalidated response.

**Redaction is a type-level property (D-11).** `GET /config/providers` returns the
provider API key in plaintext. `ProviderModel` therefore carries exactly two
fields and forbids extras, so a raw payload, a key, or a free-form raw dict is
*unrepresentable* rather than merely unused (Pitfall 11). `StructuredCallResult`
follows the same discipline: it carries identifiers, counts and a label, and its
`raw` field is **in-memory only** — never logged, never persisted, never cached.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

#: The schema a completion is constrained to. Module-level so the Protocol's
#: signature can be generic over the caller's model.
T = TypeVar("T", bound=BaseModel)


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
    """The redacted discovery outcome: identifiers only, never the response.

    `reachable=True` with an empty `providers` is HONEST, not a success: the server
    answered but advertised nothing. `error_kind` carries the distinct cause
    (`models_warming` for a cold registry, `unauthenticated` for a 401) so a caller
    can tell "still starting" from "broken" instead of reducing both to an empty
    list (D-52 / IN-02).
    """

    providers: list[ProviderModel] = Field(default_factory=list)
    reachable: bool
    version: str | None = None
    error: str | None = None
    error_kind: str | None = None


class ProbeOutcome(BaseModel):
    """A non-raising reachability result. Health probes never raise (D-08)."""

    reachable: bool
    version: str | None = None
    error: str | None = None


class StructuredCallResult(BaseModel):
    """The outcome of one structured completion — a value, never an exception.

    `extra="forbid"` is the redaction control, exactly as on `ProviderModel`:
    every field here is an identifier, a count or a short label, so a future
    contributor cannot quietly attach the response body and have it persisted.

    `raw` is the parsed response body held **in memory for the current call only**.
    It is deliberately not a column anywhere: `llm_calls` has zero JSON columns
    (guarded by `tests/db/test_no_pii_columns.py`), and a completion body is model
    prose derived from untrusted text (Pitfall P9). Never assign it to `self`,
    never log it, never cache it.
    """

    model_config = ConfigDict(extra="forbid")

    ok: bool
    data: BaseModel | None = None
    error: str | None = None
    #: In-memory only — never persisted, logged or cached.
    raw: dict | None = None
    attempts: int = 0
    provider_tokens: int | None = None
    status: str = "error"
    #: D-52's operator label: `unreachable`, `timeout`, `http_400`, … (taxonomy
    #: completed in plan 03-03).
    error_kind: str | None = None
    latency_ms: int | None = None
    #: Per-call identity. Under the retained V1 contract these are read from the
    #: response's `info.providerID` / `info.modelID` / `info.agent`. Under the V2
    #: contract `model` records the REQUESTED `OPENCODE_MODEL` and `provider` /
    #: `agent` stay NULL — the V2 `generate` response carries no served-model
    #: identity, so "authoritative served identity" is not available there
    #: (D-143/D-144).
    provider: str | None = None
    model: str | None = None
    agent: str | None = None
    server_version: str | None = None
    #: The trust-boundary OBSERVATION (success criterion 4 / T-3-19): the `type`
    #: value of each returned response part — TYPE NAMES only, never the part text.
    #: In memory for the current call; never persisted.
    part_types: list[str] | None = None
    #: The response `info` object's KEY names — names only, never values.
    info_keys: list[str] | None = None


@runtime_checkable
class LLMBackend(Protocol):
    """The ONLY surface the app depends on."""

    async def health(self) -> ProbeOutcome:
        """Server reachability (and version when reported). Never raises."""
        ...

    async def discover_models(self) -> DiscoveryResult:
        """Available provider/model ids. Never raises; never returns the body."""
        ...

    async def complete_structured(
        self,
        *,
        schema: type[T],
        system: str,
        parts: Sequence[str],
        model: str | None = None,
        agent: str | None = None,
        tools: Sequence[str] = (),
        retries: int | None = None,
    ) -> StructuredCallResult:
        """One schema-constrained completion. Never raises; failure is a value.

        `parts` is the **only** channel for untrusted content — instruction-like
        text goes there and is reported as a finding, never obeyed. `system` is a
        caller-supplied constant and there is deliberately no parameter by which
        request-derived data can reach it. `tools` defaults to empty (deny, don't
        allow); the explicit deny encoding is plan 03-06's concern.

        `retries` bounds the client-side resend loop and defaults to `None`. When
        omitted the **adapter applies `Settings.opencode_max_retries`**, so the
        retry ceiling is configuration rather than a literal (PLAT-04); an explicit
        integer is still honoured. The server-side schema retry count is a separate
        setting (`opencode_structured_retry_count`).
        """
        ...


__all__ = [
    "DiscoveryResult",
    "LLMBackend",
    "ProbeOutcome",
    "ProviderModel",
    "StructuredCallResult",
]
