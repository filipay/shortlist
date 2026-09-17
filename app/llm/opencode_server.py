"""The opencode HTTP backend — health (D-08), discovery (D-09), structured calls.

Three endpoints, all narrow:

* ``GET /global/health`` — reachability, and the version when the server reports
  one. A failure is `reachable=False`, never an exception: `docker compose up`
  must not depend on an LLM backend being up (D-08).
* ``GET /config/providers`` — the subscription-scoped provider/model set the user
  actually configured. The full vendor catalogue endpoint (``/provider``, ~6 MB,
  217 providers) is deliberately **not** referenced anywhere in this module (D-09);
  `tests/llm/test_discovery_redaction.py` asserts both the behaviour and the
  absence of that path.
* ``POST /session`` then ``POST /session/{id}/message`` — one schema-constrained
  completion. The request vocabulary lives in `app.llm.contract` (D-54) and the
  bodies are built by the pure `app.llm.builders`.

The discovery response carries the provider API key in plaintext, so it is parsed
straight into identifiers and never logged, never stored on an attribute, never
cached and never returned (D-11 / T-01-29). A completion response is model prose
derived from untrusted text and is held only in the local `StructuredCallResult`
for the current call (Pitfall P9).

**Failure is a value.** Every method here is total: an exception is converted to
a result object rather than raised, so a broken backend can never 500 a route.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

import httpx
import structlog
from pydantic import ValidationError

from app.config import settings
from app.llm.base import (
    DiscoveryResult,
    ProbeOutcome,
    ProviderModel,
    StructuredCallResult,
    T,
)
from app.llm.builders import to_message_body
from app.llm.contract import (
    MESSAGE_MODEL_FIELDS,
    MESSAGE_PATH,
    SESSION_ID_FIELD,
    SESSION_ID_PREFIX,
    SESSION_PATH,
    STRUCTURED_ERROR_MESSAGE_PATH,
    STRUCTURED_ERROR_NAME,
    STRUCTURED_ERROR_RETRIES_PATH,
    STRUCTURED_RESPONSE_PATH,
)

log = structlog.get_logger(__name__)

GLOBAL_HEALTH_PATH = "/global/health"
CONFIG_PROVIDERS_PATH = "/config/providers"

# --- D-52 operator-facing causes ---------------------------------------------
#
# `status` must stay inside the four legal `llm_calls.status` values
# (`ok`/`invalid`/`timeout`/`error`, mirroring `ck_llm_calls_status`); the
# specific CAUSE lives in `error_kind`, so a failure is never reduced to a bare
# red/green badge and the CHECK constraint is never extended ad hoc.
ERROR_KIND_UNREACHABLE = "unreachable"
ERROR_KIND_TIMEOUT = "timeout"
ERROR_KIND_INVALID = "invalid"
ERROR_KIND_MODEL_NOT_FOUND = "model_not_found"
ERROR_KIND_INVALID_SESSION = "invalid_session"
#: Prefix for a non-200 response, e.g. `http_400`.
HTTP_ERROR_KIND_PREFIX = "http_"
#: A non-200 body excerpt is a diagnostic, not a copy: enough to recognise the
#: error, never the whole body (P9 / T-3-05).
NON_200_BODY_EXCERPT_CHARS = 200


def parse_providers(payload: object) -> list[ProviderModel]:
    """Extract `(provider_id, model_id)` pairs from a discovery payload.

    **Assumptions Log A2 is answered, and was wrong.** The live shape was read from
    opencode 1.18.31 on 2026-09-17: ``providers[].models`` is a JSON **object**
    keyed by model id (not a list of ``{"id": …}`` objects), and the
    credential-adjacent field is **``key``** (not ``api_key``). The function now
    accepts **both** shapes, so the shipped legacy-list fixture keeps working while
    the live object shape yields its model ids (Pitfall P1).

    Tolerant by design: a payload that is not a mapping, a provider with no usable
    `models`, and a malformed entry each contribute nothing — the parse fails to
    an empty list rather than raising, and the caller gets a deterministic result
    either way.

    Only the two identifiers are copied. Provider-level extras (notably `key`,
    `env`, `options`, `source`) are read past, never assigned; for the object
    shape the model **keys** are copied and the per-model metadata **values** are
    never touched — they are the realistic place a future secret could hide.
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
        if isinstance(models, dict):
            # Live 1.18.31 shape: {modelID: metadata}. Copy the KEYS only.
            model_ids = [model_id for model_id in models if isinstance(model_id, str)]
        elif isinstance(models, list):
            # Legacy shape: [{"id": modelID, ...}, …].
            model_ids = [
                model.get("id") for model in models if isinstance(model, dict)
            ]
        else:
            continue

        for model_id in model_ids:
            if not isinstance(model_id, str) or not model_id:
                continue
            found.append(ProviderModel(provider_id=provider_id, model_id=model_id))

    return sorted(found, key=lambda entry: (entry.provider_id, entry.model_id))


class OpenCodeServerBackend:
    """Reachability, discovery and one structured completion over HTTP."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        password: str | None = None,
        timeout: float | None = None,
        completion_timeout: float | None = None,
    ) -> None:
        self._base_url = base_url if base_url is not None else settings.opencode_base_url
        self._password = (
            password if password is not None else settings.opencode_server_password
        )
        self._timeout = (
            timeout if timeout is not None else settings.opencode_timeout_seconds
        )
        # A completion is a different order of magnitude from a health probe, so
        # it gets its own ceiling instead of reusing the 5-second `_timeout`
        # (Pitfall P4).
        self._completion_timeout = (
            completion_timeout
            if completion_timeout is not None
            else settings.opencode_completion_timeout_seconds
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

    def _completion_client(self) -> httpx.AsyncClient:
        """A client bounded by the COMPLETION ceiling, not the 5s health one."""
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._completion_timeout,
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

    async def _resolve_model(
        self, model: str | None = None
    ) -> tuple[str, str] | StructuredCallResult:
        """Resolve a bare model id to `(provider_id, model_id)` via discovery.

        `OPENCODE_MODEL` is a bare model id (e.g. ``deepseek-v4.1-flash``) while
        the message body needs ``{providerID, modelID}``. The provider is
        **derived from the server's own discovery response**, never hard-coded
        (Assumptions Log A5's mitigation). Ambiguity — one model id offered under
        two providers — resolves deterministically by sorted provider id.

        **Fail loud.** On a miss, or when discovery is unreachable, this returns an
        `ok=False` result naming the offending model id rather than silently
        omitting `model` — otherwise a wrong `OPENCODE_MODEL` would be
        indistinguishable from a call that worked.
        """
        wanted = model if model is not None else settings.opencode_model
        discovery = await self.discover_models()
        if not discovery.reachable:
            return StructuredCallResult(
                ok=False,
                status="error",
                error=discovery.error or "model discovery failed",
                error_kind=ERROR_KIND_UNREACHABLE,
            )
        matches = sorted(
            (entry.provider_id, entry.model_id)
            for entry in discovery.providers
            if entry.model_id == wanted
        )
        if not matches:
            return StructuredCallResult(
                ok=False,
                status="error",
                error=f"model {wanted!r} is not configured on this server",
                error_kind=ERROR_KIND_MODEL_NOT_FOUND,
            )
        provider_id, model_id = matches[0]
        return provider_id, model_id

    async def _create_session(
        self, client: httpx.AsyncClient
    ) -> str | StructuredCallResult:
        """`POST /session` with an empty body; read the session id.

        An empty `{}` is schema-valid (no required properties) and selects the
        server's defaults. A response with no usable `ses…` id is a value, not an
        exception.
        """
        response = await client.post(SESSION_PATH, json={})
        if response.status_code != 200:
            return StructuredCallResult(
                ok=False,
                status="error",
                error=f"session create returned HTTP {response.status_code}",
                error_kind=f"{HTTP_ERROR_KIND_PREFIX}{response.status_code}",
            )
        body = response.json()
        session_id = body.get(SESSION_ID_FIELD) if isinstance(body, dict) else None
        if not isinstance(session_id, str) or not session_id.startswith(
            SESSION_ID_PREFIX
        ):
            return StructuredCallResult(
                ok=False,
                status="error",
                error="session create returned no usable id",
                error_kind=ERROR_KIND_INVALID_SESSION,
            )
        return session_id

    async def complete_structured(
        self,
        *,
        schema: type[T],
        system: str,
        parts: Sequence[str],
        model: str | None = None,
        agent: str | None = None,
        tools: Sequence[str] = (),
        retries: int = 2,
    ) -> StructuredCallResult:
        """One schema-constrained completion: session → message → validated result.

        A total function (failure-as-value, D-08's discipline): the caller always
        receives a classified, counted `StructuredCallResult` and this method
        never raises. `status` is always one of the four legal `llm_calls.status`
        values; the specific cause is in `error_kind` (D-52).

        **Two retry layers, deliberately different:**

        * the SERVER re-asks the model on a schema failure, bounded by
          `format.retryCount` (`settings.opencode_structured_retry_count`);
        * the CLIENT resends on a transport failure or timeout, bounded by the
          `retries` argument (whose default is `settings.opencode_max_retries`).

        A schema failure is never retried client-side — the server already did its
        retries, and double-retrying would inflate the attempt count the operator
        reads. `attempts` is the server's own `info.error.data.retries` when the
        server supplies one, and the client's issued-request count otherwise.

        `parts` is the only channel for untrusted content; `system` is passed
        through untouched. `tools` is accepted for the port contract (default
        empty = deny) but is not sent yet: the documented deny encoding lands in
        plan 03-06 (Pitfall P5).
        """
        started = time.perf_counter()
        try:
            resolved = await self._resolve_model(model)
            if isinstance(resolved, StructuredCallResult):
                return resolved
            provider_id, model_id = resolved

            # D-12 telemetry: the server version only lives on /global/health
            # (Pitfall P12). A health failure must not fail the call.
            try:
                server_version: str | None = (await self.health()).version
            except Exception:  # noqa: BLE001 — version is telemetry, not the call
                server_version = None

            # The caller's ceiling governs the loop; `Settings` supplies only the
            # DEFAULT, so a future caller passing a different bound is honoured
            # (PLAT-04: no literal ceiling).
            budget = retries if retries is not None else settings.opencode_max_retries
            budget = max(1, int(budget))
            issued = 0
            last_failure: StructuredCallResult | None = None

            async with self._completion_client() as client:
                session_id = await self._create_session(client)
                if isinstance(session_id, StructuredCallResult):
                    return session_id
                body = to_message_body(
                    schema=schema,
                    system=system,
                    parts=parts,
                    provider_id=provider_id,
                    model_id=model_id,
                    agent=agent,
                    # The SERVER-side schema ceiling is configuration (PLAT-04),
                    # distinct from the client resend ceiling above.
                    retry_count=settings.opencode_structured_retry_count,
                )
                for _attempt in range(1, budget + 1):
                    try:
                        response = await client.post(
                            MESSAGE_PATH.format(session_id=session_id), json=body
                        )
                    except httpx.TimeoutException as exc:
                        issued += 1
                        # Failing to ESTABLISH a connection is "unreachable"; a
                        # connected-but-slow response is a genuine timeout.
                        if isinstance(exc, httpx.ConnectTimeout):
                            last_failure = _failure(
                                status="error",
                                error_kind=ERROR_KIND_UNREACHABLE,
                                error=f"{type(exc).__name__}: {exc}",
                                attempts=issued,
                                started=started,
                                provider=provider_id,
                                model=model_id,
                                agent=agent,
                                server_version=server_version,
                            )
                        else:
                            last_failure = _failure(
                                status="timeout",
                                error_kind=ERROR_KIND_TIMEOUT,
                                error=f"{type(exc).__name__}: {exc}",
                                attempts=issued,
                                started=started,
                                provider=provider_id,
                                model=model_id,
                                agent=agent,
                                server_version=server_version,
                            )
                        continue
                    except httpx.TransportError as exc:
                        issued += 1
                        last_failure = _failure(
                            status="error",
                            error_kind=ERROR_KIND_UNREACHABLE,
                            error=f"{type(exc).__name__}: {exc}",
                            attempts=issued,
                            started=started,
                            provider=provider_id,
                            model=model_id,
                            agent=agent,
                            server_version=server_version,
                        )
                        continue
                    issued += 1
                    # A response arrived: classify and stop. Schema failures are
                    # NOT retried here — the server already ran `format.retryCount`.
                    return _classify_message_response(
                        response,
                        schema=schema,
                        provider_id=provider_id,
                        model_id=model_id,
                        agent=agent,
                        server_version=server_version,
                        attempts=issued,
                        started=started,
                    )

            if last_failure is not None:
                return last_failure
            return _failure(
                status="error",
                error_kind=ERROR_KIND_UNREACHABLE,
                error="no attempt was issued",
                attempts=issued,
                started=started,
                provider=provider_id,
                model=model_id,
                agent=agent,
                server_version=server_version,
            )
        except httpx.TimeoutException as exc:  # noqa: BLE001 — a completion never raises
            return _failure(
                status="error" if isinstance(exc, httpx.ConnectTimeout) else "timeout",
                error_kind=(
                    ERROR_KIND_UNREACHABLE
                    if isinstance(exc, httpx.ConnectTimeout)
                    else ERROR_KIND_TIMEOUT
                ),
                error=f"{type(exc).__name__}: {exc}",
                attempts=0,
                started=started,
            )
        except httpx.TransportError as exc:  # noqa: BLE001 — a completion never raises
            return _failure(
                status="error",
                error_kind=ERROR_KIND_UNREACHABLE,
                error=f"{type(exc).__name__}: {exc}",
                attempts=0,
                started=started,
            )
        except Exception as exc:  # noqa: BLE001 — a completion never raises
            return _failure(
                status="error",
                error_kind=type(exc).__name__,
                error=f"{type(exc).__name__}: {exc}",
                attempts=0,
                started=started,
            )


def _failure(
    *,
    status: str,
    error_kind: str,
    error: str,
    attempts: int,
    started: float,
    provider: str | None = None,
    model: str | None = None,
    agent: str | None = None,
    server_version: str | None = None,
) -> StructuredCallResult:
    """One classified failure. `raw` is always None here (P9 / T-3-05).

    The non-200 excerpt lives in `error` (bounded); the response BODY is never
    carried on a result that a caller might persist.
    """
    return StructuredCallResult(
        ok=False,
        status=status,
        error=error,
        error_kind=error_kind,
        attempts=attempts,
        raw=None,
        latency_ms=_elapsed_ms(started),
        provider=provider,
        model=model,
        agent=agent,
        server_version=server_version,
    )


def _bounded_excerpt(response: object) -> str:
    """Up to `NON_200_BODY_EXCERPT_CHARS` characters of a response body, or `""`."""
    try:
        text = response.text  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — an unreadable body yields no excerpt
        return ""
    if not isinstance(text, str):
        return ""
    return text[:NON_200_BODY_EXCERPT_CHARS]


def _classify_message_response(
    response: object,
    *,
    schema: type[T],
    provider_id: str,
    model_id: str,
    agent: str | None,
    server_version: str | None,
    attempts: int,
    started: float,
) -> StructuredCallResult:
    """Map one completion response onto the four legal statuses (D-52).

    Validated → `ok`; the `StructuredOutputError` envelope → `invalid` with the
    server's own attempt count; a `ValidationError` → `invalid` with its first
    message; a non-200 → `error`/`http_<code>`; an unparseable 200 → `error` naming
    the parse exception.
    """
    status_code = getattr(response, "status_code", None)
    if status_code != 200:
        excerpt = _bounded_excerpt(response)
        detail = f": {excerpt}" if excerpt else ""
        return _failure(
            status="error",
            error_kind=f"{HTTP_ERROR_KIND_PREFIX}{status_code}",
            error=f"message send returned HTTP {status_code}{detail}",
            attempts=attempts,
            started=started,
            provider=provider_id,
            model=model_id,
            agent=agent,
            server_version=server_version,
        )

    try:
        payload = response.json()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 — an unparseable 200 is a classified failure
        return _failure(
            status="error",
            error_kind=type(exc).__name__,
            error=f"{type(exc).__name__}: {exc}",
            attempts=attempts,
            started=started,
            provider=provider_id,
            model=model_id,
            agent=agent,
            server_version=server_version,
        )

    # `payload` is model prose derived from untrusted text. It is consumed here and
    # held only on a SUCCESSFUL result's `raw` (in memory for this call) — never
    # assigned to `self`, logged, cached or persisted (P9).
    info = payload.get("info") if isinstance(payload, dict) else None
    if not isinstance(info, dict):
        return _failure(
            status="invalid",
            error_kind=ERROR_KIND_INVALID,
            error="response carried no info object",
            attempts=attempts,
            started=started,
            server_version=server_version,
        )

    identity = {
        "provider": _identity(info, 0) or provider_id,
        "model": _identity(info, 1) or model_id,
        "agent": _agent(info) or agent,
    }

    # `info.error` is an ENVELOPE (P7): the name is at the top level and the
    # message/attempt count are nested under `.data`.
    envelope = info.get("error")
    if isinstance(envelope, dict) and envelope.get("name"):
        name = str(envelope["name"])
        if name == STRUCTURED_ERROR_NAME:
            data = envelope.get("data")
            data = data if isinstance(data, dict) else {}
            message = data.get(STRUCTURED_ERROR_MESSAGE_PATH[-1])
            server_retries = data.get(STRUCTURED_ERROR_RETRIES_PATH[-1])
            server_attempts = (
                int(server_retries)
                if isinstance(server_retries, int)
                and not isinstance(server_retries, bool)
                else attempts
            )
            cause = (
                f"{STRUCTURED_ERROR_NAME}: {message}"
                if isinstance(message, str) and message
                else STRUCTURED_ERROR_NAME
            )
            return _failure(
                status="invalid",
                error_kind=ERROR_KIND_INVALID,
                error=cause,
                attempts=server_attempts,
                started=started,
                server_version=server_version,
                **identity,
            )
        # Any other provider error envelope is a failure too, never a silent
        # success; the error's own name is the operator-facing cause.
        return _failure(
            status="error",
            error_kind=name,
            error=f"provider error: {name}",
            attempts=attempts,
            started=started,
            server_version=server_version,
            **identity,
        )

    structured = info.get(STRUCTURED_RESPONSE_PATH[-1])
    if structured is None:
        return _failure(
            status="invalid",
            error_kind=ERROR_KIND_INVALID,
            error="response carried no structured payload",
            attempts=attempts,
            started=started,
            server_version=server_version,
            **identity,
        )

    try:
        data = schema.model_validate(structured)
    except ValidationError as exc:
        errors = exc.errors()
        first = errors[0] if errors else None
        detail = first.get("msg") if isinstance(first, dict) else None
        return _failure(
            status="invalid",
            error_kind=ERROR_KIND_INVALID,
            error=(
                f"validation failed: {detail}" if detail else "validation failed"
            ),
            attempts=attempts,
            started=started,
            server_version=server_version,
            **identity,
        )

    return StructuredCallResult(
        ok=True,
        data=data,
        status="ok",
        raw=payload,
        attempts=attempts,
        provider_tokens=_output_tokens(info),
        latency_ms=_elapsed_ms(started),
        provider=identity["provider"],
        model=identity["model"],
        agent=identity["agent"],
        server_version=server_version,
    )


def _elapsed_ms(started: float) -> int:
    """Whole milliseconds since `started` (a `time.perf_counter()` reading)."""
    return int((time.perf_counter() - started) * 1000)


def _output_tokens(info: dict) -> int | None:
    """`info.tokens.output` as an int, or None when the shape is unexpected."""
    tokens = info.get("tokens")
    if not isinstance(tokens, dict):
        return None
    value = tokens.get("output")
    return int(value) if isinstance(value, int) else None


def _identity(info: dict, index: int) -> str | None:
    """One of `info`'s `providerID`/`modelID` values, or None when unusable."""
    value = info.get(MESSAGE_MODEL_FIELDS[index])
    return value if isinstance(value, str) and value else None


def _agent(info: dict) -> str | None:
    """`info.agent` when the server reports one."""
    value = info.get("agent")
    return value if isinstance(value, str) and value else None


__all__ = [
    "CONFIG_PROVIDERS_PATH",
    "ERROR_KIND_INVALID",
    "ERROR_KIND_INVALID_SESSION",
    "ERROR_KIND_MODEL_NOT_FOUND",
    "ERROR_KIND_TIMEOUT",
    "ERROR_KIND_UNREACHABLE",
    "GLOBAL_HEALTH_PATH",
    "HTTP_ERROR_KIND_PREFIX",
    "NON_200_BODY_EXCERPT_CHARS",
    "OpenCodeServerBackend",
    "parse_providers",
]
