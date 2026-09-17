# Phase 3: LLM Port + Structured Output - Pattern Map

**Mapped:** 2026-09-17
**Files analyzed:** 41 (18 production, 19 test, 4 docs/config)
**Analogs found:** 37 / 41 (4 have no close analog — see bottom)

> **Tracked-source gate (#3645):** every analog path below was verified with
> `git ls-files -- <path>` → non-empty (257 tracked files at time of mapping). No
> `.gsd/capabilities/*` mirror path is emitted.

> **Not a TypeScript repo.** Role vocabulary is Python: route/handler, service,
> repository, Pydantic schema/model, Protocol port, adapter, Alembic migration,
> pytest test, Jinja template, Settings field.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/llm/base.py` | port (Protocol) | request-response | `app/llm/base.py` (self) | exact |
| `app/llm/contract.py` (NEW) | config/constants | transform (pure) | `app/llm/opencode_server.py:29-30` + `app/domain/sanitize.py` constants | role-match |
| `app/llm/builders.py` (NEW) | utility | transform (pure) | `app/pipeline/stages.py:60-115` (`normalise_listing`) | role-match |
| `app/llm/opencode_server.py` | adapter (HTTP) | request-response | `app/llm/opencode_server.py` (self) | exact |
| `app/llm/__init__.py` | DI factory | request-response | `app/llm/__init__.py` (self) | exact |
| `app/domain/schemas/__init__.py` (NEW) | domain package marker | — | `app/domain/__init__.py` | exact |
| `app/domain/schemas/probe.py` (NEW) | Pydantic schema | transform | `app/llm/base.py:21-42` (`ProviderModel`) | role-match |
| `app/db/repositories/llm_call_repo.py` (NEW) | repository | CRUD (insert + read) | `app/db/repositories/event_repo.py:148-185` + `run_repo.py` | exact (role+flow) |
| `alembic/versions/0003_llm_call_server_version.py` (NEW) | migration | schema DDL | `alembic/versions/0002_queue_filter_and_run_reason.py:45-103` | exact |
| `app/db/models.py` | ORM model | CRUD | `app/db/models.py:440-469` (self) | exact |
| `app/config.py` | config (Settings) | — | `app/config.py:30-37` (self) | exact |
| `app/api/settings.py` | route/handler | request-response | `app/api/settings.py:211-333` (self) | exact |
| `app/api/health.py` | route/handler | request-response | `app/api/health.py:40-112` (self) | exact (guard: do not change shape) |
| `app/api/deps.py` | middleware seam | request-response | `app/api/deps.py:14-22` (self) | exact |
| `app/web/routes.py` | route/handler | request-response | `app/web/routes.py:71-90` (self) | exact (optional badge) |
| `app/pipeline/run.py` | pipeline stage/seam | batch | `app/pipeline/run.py:247-283, 549-595` (self) | exact |
| `app/pipeline/stages.py` | pipeline stage | batch/transform | `app/pipeline/stages.py:60-115` (self) | exact |
| `app/domain/models.py` | domain dataclass | transform | `app/domain/models.py:37-84` (self) | exact |
| `app/domain/sanitize.py` | domain module | transform | `app/domain/sanitize.py:96-125` (self) | exact (read-only — fields already exist) |
| `app/db/repositories/listing_repo.py` | repository | CRUD (upsert) | `app/db/repositories/listing_repo.py:37-60, 123-126` (self) | exact (read-only) |
| `app/web/templates/html/settings.html` | template | request-response | `app/web/templates/html/settings.html` (self) | exact |
| `app/web/templates/html/_llm_test_result.html` (NEW, optional) | template partial | request-response | `app/web/templates/html/_run_status.html` | role-match |
| `tests/llm/fixtures/opencode-doc.json` (NEW) | test fixture | — | `tests/fixtures/opencode_providers.json` | role-match |
| `tests/llm/test_contract_snapshot.py` (NEW) | test (unit/guard) | — | `tests/llm/test_discovery_redaction.py` + `tests/test_import_discipline.py` | role-match |
| `tests/llm/test_contract_live.py` (NEW) | test (live lane) | — | `tests/live/test_probe_live.py` | exact |
| `tests/llm/test_complete_structured.py` (NEW) | test (unit) | — | `tests/llm/test_discovery_redaction.py:53-91` (`Recorder`) | exact |
| `tests/llm/test_salvage.py` (NEW) | test (unit) | — | `tests/llm/test_discovery_redaction.py` | role-match |
| `tests/llm/test_trust_boundary.py` (NEW) | test (guard) | — | `tests/test_import_discipline.py` + `tests/domain/test_injection_patterns.py` | role-match |
| `tests/api/test_llm_selftest.py` (NEW) | test (integration) | — | `tests/api/test_settings_page.py` + `tests/api/test_settings_reset.py` | role-match |
| `tests/db/test_llm_call_repo.py` (NEW) | test (integration) | — | `tests/db/test_search_repo_writes.py` | exact |
| `tests/pipeline/test_injection_finding.py` (NEW) | test (integration) | — | `tests/pipeline/test_filter_stage.py` | exact |
| `tests/llm/test_discovery_redaction.py` | test (MODIFY) | — | self | exact |
| `tests/conftest.py` | test fixture (MODIFY) | — | self:33-45 | exact |
| `tests/test_auth_seam.py` (MODIFY) | test guard | — | self:28-31 | exact |
| `tests/test_config.py` (MODIFY) | test guard | — | self:28-66 | exact |
| `tests/api/test_settings_page.py` (MODIFY if HTMX) | test guard | — | self:54-59 | exact |
| `tests/db/test_migration_contract.py` (MODIFY) | test guard | — | self:294, 305, 500 | exact |
| `tests/api/test_health.py` (MODIFY? guard only) | test guard | — | self:253-257, 394 | exact |
| `tests/test_import_discipline.py` (MODIFY) | test guard | — | self:14-18, 64-82 | exact |
| `tests/fixtures/opencode_providers.json` (MODIFY) | test fixture | — | self | exact |
| `docs/runbook-opencode-contract.md` (NEW) or `docs/runbook-compose-smoke.md` (MODIFY) | docs | — | `docs/runbook-compose-smoke.md` + `docs/probes/README.md` | role-match |
| `.env.example` (MODIFY) | config | — | self | exact |
| `compose.yml` (MODIFY) | config | — | self:15-29 | exact |

---

## Pattern Assignments

### `app/llm/base.py` (port, request-response)

**Analog:** `app/llm/base.py` (extend in place)

**Module docstring discipline** (lines 1-12) — state the phase boundary and the redaction
rationale at module top; this repo documents *why* a type is narrow:
```python
"""The LLM backend port — Phase 1 scope: health and discovery only.
...
**Redaction is a type-level property (D-11).** `GET /config/providers` returns the
provider API key in plaintext. `ProviderModel` therefore carries exactly two
fields and forbids extras, so a raw payload, a key, or a free-form raw dict is
*unrepresentable* rather than merely unused (Pitfall 11).
"""
```

**Imports** (lines 14-18):
```python
from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field
```

**Redaction-first typed model** (lines 21-42) — copy `extra="forbid"` and the "identifiers only"
docstring style for `StructuredCallResult`:
```python
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
```

**Port Protocol + the reserved extension point** (lines 52-62) — the docstring already names
Phase 3; keep `health()`'s signature unchanged (RESEARCH §LLMBackend Port Extension deviation 1):
```python
@runtime_checkable
class LLMBackend(Protocol):
    """The ONLY surface the app depends on. Phase 3 adds `complete_structured`."""

    async def health(self) -> ProbeOutcome:
        """Server reachability (and version when reported). Never raises."""
        ...

    async def discover_models(self) -> DiscoveryResult:
        """Available provider/model ids. Never raises; never returns the body."""
        ...
```

**`__all__`** (line 65) — every module ends with an explicit `__all__`; add
`StructuredCallResult` there:
```python
__all__ = ["DiscoveryResult", "LLMBackend", "ProbeOutcome", "ProviderModel"]
```

**Validation:** `StructuredCallResult` per RESEARCH §Schema-Violation Degradation:
`model_config = ConfigDict(extra="forbid")`, fields `ok, data, error, raw, attempts,
provider_tokens` plus D-52 additions `status, error_kind, latency_ms, provider, model,
agent, server_version`. `raw` is in-memory only — never persisted (Pitfall P9).

---

### `app/llm/contract.py` (NEW — constants, pure)

**Analog:** `app/llm/opencode_server.py:29-30` (module-level path constants) + `app/domain/sanitize.py`
(module-level tuples) — this repo puts pinned vocabularies at module scope as UPPER_CASE, with a
docstring naming the decision.

**Constant declaration pattern** (`app/llm/opencode_server.py:29-30`):
```python
GLOBAL_HEALTH_PATH = "/global/health"
CONFIG_PROVIDERS_PATH = "/config/providers"
```

**Vocabulary-as-tuple pattern** (`app/domain/sanitize.py` INJECTION_PATTERNS / `event_repo.py:60`
`EVENT_TYPES`) — a tuple/frozenset with a comment naming the CHECK constraint it mirrors:
```python
#: The six event types, mirroring `ck_listing_events_event_type` from migration 0001
#: exactly. This is the allow-list the route validates against — a second vocabulary
#: is never minted, and widening it is a coordinated migration plus a change here.
EVENT_TYPES: tuple[str, ...] = ("save", "unsave", "hide", "unhide", "shortlist", "view")
```

**Required module shape** (RESEARCH §Pinning Strategy A, D-54/D-56) — one constant per surface,
docstring naming the live server version, `from __future__ import annotations`, and `__all__`:
```python
DOC_PATH = "/doc"
SESSION_PATH = "/session"
MESSAGE_PATH = "/session/{session_id}/message"
FORMAT_FIELD = "format"                     # NOT "outputFormat" (D-54)
FORMAT_TYPE_FIELD = "type"
FORMAT_SCHEMA_FIELD = "schema"
FORMAT_RETRY_FIELD = "retryCount"
FORMAT_JSON_SCHEMA_TYPE = "json_schema"
FORMAT_INNER_KEYS = (FORMAT_TYPE_FIELD, FORMAT_SCHEMA_FIELD, FORMAT_RETRY_FIELD)
FORMAT_REQUIRED_KEYS = (FORMAT_TYPE_FIELD, FORMAT_SCHEMA_FIELD)
STRUCTURED_RESPONSE_PATH = ("info", "structured")     # live 1.18.31; NOT structured_output
STRUCTURED_ERROR_NAME = "StructuredOutputError"
STRUCTURED_ERROR_RETRIES_PATH = ("info", "error", "data", "retries")
MESSAGE_MODEL_FIELDS = ("providerID", "modelID")      # message body
SESSION_MODEL_FIELDS = ("id", "providerID")           # session body — DIFFERENT
```

**Guard:** `tests/test_import_discipline.py:14-18` forbids `httpx` under `app/domain` — this is
why the constants live in `app/llm/`, not `app/domain/`. `contract.py` must import nothing but
`__future__` + `typing`.

---

### `app/llm/builders.py` (NEW — pure request builders)

**Analog:** `app/pipeline/stages.py:60-115` (`normalise_listing`) — the repo's canonical pure
transform: one function, no I/O, docstring states the purity contract.

**Purity + docstring pattern** (`app/pipeline/stages.py:60-65`):
```python
def normalise_listing(raw: RawListing) -> NormalisedListing:
    """Board-shaped `RawListing` -> canonical `NormalisedListing`.

    Pure: one function, no I/O, so both dedup keys are unit-testable without a
    database or a network (Pattern 2).
    """
```

**Core pattern** (RESEARCH §Code Examples "Request builders"; all key names from `contract.py`):
```python
def to_message_parts(texts: Sequence[str]) -> list[dict[str, str]]:
    return [{"type": TEXT_PART_TYPE, "text": text} for text in texts]


def to_message_body(
    *,
    schema: type[BaseModel],
    system: str,
    parts: Sequence[str],
    provider_id: str,
    model_id: str,
    agent: str | None = None,
    retry_count: int | None = None,
    tools: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    """Emit EXACTLY the wire shape. Every key name comes from app/llm/contract.py."""
    body: dict[str, Any] = {
        "parts": to_message_parts(parts),
        "system": system,
        "model": {"providerID": provider_id, "modelID": model_id},
        FORMAT_FIELD: {
            FORMAT_TYPE_FIELD: FORMAT_JSON_SCHEMA_TYPE,
            FORMAT_SCHEMA_FIELD: schema.model_json_schema(),
        },
    }
    if retry_count is not None:
        body[FORMAT_FIELD][FORMAT_RETRY_FIELD] = retry_count
    if agent is not None:
        body["agent"] = agent
    if tools is not None:
        body["tools"] = dict(tools)
    return body
```

**Validation:** `parts` is ergonomic `list[str]` at the PORT but `[{"type":"text","text":...}]` on
the WIRE — document the translation in the builder docstring so it is not "fixed" later. Keep
`retry_count` optional (`FORMAT_REQUIRED_KEYS` excludes `retryCount`).

---

### `app/llm/opencode_server.py` (adapter, request-response)

**Analog:** `app/llm/opencode_server.py` (extend in place — `parse_providers` fix +
`complete_structured`).

**Imports + module constants + log** (lines 19-30):
```python
from __future__ import annotations

import httpx
import structlog

from app.config import settings
from app.llm.base import DiscoveryResult, ProbeOutcome, ProviderModel

log = structlog.get_logger(__name__)

GLOBAL_HEALTH_PATH = "/global/health"
CONFIG_PROVIDERS_PATH = "/config/providers"
```

**`parse_providers` — the bug to fix** (lines 59-61) — `models` is a **list** here but a **dict**
on live opencode 1.18.31 (Pitfall P1):
```python
        models = provider.get("models")
        if not isinstance(models, list):
            continue
        for model in models:
            if not isinstance(model, dict):
                continue
            model_id = model.get("id")
```
Fix: accept **both** shapes — dict keys → model ids; list items → `{"id": ...}`. Copy **only**
identifiers; the live credential-adjacent field is **`key`**, not `api_key` (D-11).

**Constructor / auth / bounded client** (lines 76-107) — copy verbatim; `complete_structured`
reuses `_client()`:
```python
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
        """Basic auth only when a password is configured (D-07)."""
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
```

**Total-function / failure-as-value** (lines 109-129 and 131-155) — `complete_structured` MUST
follow this exact shape: an outer `try/except Exception` with `# noqa: BLE001` returning a value,
never raising. Note the redaction comment at 141-145:
```python
    async def health(self) -> ProbeOutcome:
        """`GET /global/health`. `reachable=False` on any failure (D-08)."""
        try:
            async with self._client() as client:
                response = await client.get(GLOBAL_HEALTH_PATH)
        except Exception as exc:  # noqa: BLE001 — boot tolerance
            return ProbeOutcome(reachable=False, error=type(exc).__name__)
        ...
        # The body carries a plaintext provider credential. It is consumed
        # as an argument to the parse and never assigned to an attribute,
        # never logged, never cached to disk and never returned; only the
        # identifiers extracted by `parse_providers` leave this block.
        providers = parse_providers(response.json())
```

**Structured log pattern** (lines 149-154) — counts only, never content:
```python
        log.info(
            "llm.discovery",
            backend="opencode_server",
            provider_count=len({entry.provider_id for entry in providers}),
            model_count=len(providers),
        )
```

**Core `complete_structured` pattern** (RESEARCH §Architecture Patterns diagram + §Code Examples
"Reading the result"): session create → message send → read `info.structured` → classify:
```python
body = response.json()                       # {"info": AssistantMessage, "parts": [...]}
info = body["info"]                          # both keys required by the 200 schema
structured = info.get(STRUCTURED_RESPONSE_PATH[-1])   # -> the validated payload
error      = info.get("error")
if error is not None and error.get("name") == STRUCTURED_ERROR_NAME:
    data     = error["data"]                 # required: message, retries
    attempts = data["retries"]               # SERVER's attempt count (P7)
    message  = data["message"]
provider_id = info["providerID"]; model_id = info["modelID"]; agent = info["agent"]
tokens = info["tokens"]; prompt_tokens = tokens["input"]; completion_tokens = tokens["output"]
```

**Error taxonomy → `llm_calls.status`** (four legal values only): `ok` / `invalid` (schema or
`StructuredOutputError`) / `timeout` (`httpx.TimeoutException`) / `error` (transport, non-200,
unparseable JSON). `error_kind` carries D-52's operator label (`unreachable`, `http_400`, …).

**Retry loop** (RESEARCH §Bounded retry) — explicit `for attempt in range(1, settings.opencode_max_retries + 1)`
so per-attempt classification stays visible; do **not** send `{"*": false}` in `tools` (P5);
encode the deny explicitly and document it.

**Salvage** (RESEARCH §The salvage path) — `pydantic_core.from_json(payload, allow_partial=True)`
then `schema.model_validate`; tolerated error types are an **explicit allow-list**
(`TOLERATED_SCHEMA_ERRORS = frozenset({"missing", "int_parsing"})`). `PydanticUseDefault` only
works on fields that **have a default** (P11).

**`__all__`** (lines 158-163) — extend with `complete_structured` is a method, not exported; add any
new module constant.

---

### `app/llm/__init__.py` (DI factory)

**Analog:** `app/llm/__init__.py` (self)

**DI factory** (lines 7-14) — unchanged shape; tests override it:
```python
def get_llm_backend() -> LLMBackend:
    """FastAPI dependency: the configured backend, built per request.

    A function rather than a module-level instance for two reasons: a test can
    override it (the default lane must never touch a live server), and no client
    state is shared between requests.
    """
    return OpenCodeServerBackend()
```

**`__all__`** (lines 17-25) — re-export new `StructuredCallResult` and `contract` symbols as
appropriate. **Must not** re-export `httpx`-touching symbols that would let callers bypass the port.

---

### `app/domain/schemas/probe.py` (NEW — Pydantic schema, pure)

**Analog:** `app/llm/base.py:21-42` (`ProviderModel`) for the redaction-first Pydantic style;
`app/domain/models.py:37-84` for the pure-domain convention.

**Pure-domain constraint** (`app/domain/models.py:1-8`):
```python
"""Pure domain types.
...
This module imports no I/O — enforced by `tests/test_import_discipline.py` (D-24).
"""
```

**Schema pattern** — small (D-51), every tolerated field has a default (P11), and RESEARCH §V5
recommends `extra="ignore"` for `ProbeResult` (a model that added a field is not a failure) while
wire-adjacent models stay `extra="forbid"`:
```python
class ProbeResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    acknowledged: bool = False
    instruction_detected: bool = False
    echo: str = ""
```

**Testing:** pure Pydantic — test `model_json_schema()` and `model_validate` with no server.

---

### `app/db/repositories/llm_call_repo.py` (NEW — repository, CRUD)

**Analog:** `app/db/repositories/event_repo.py:148-185` (`append_event`) — the canonical keyword-only
writer with `now` pinning, allow-list validation, SAVEPOINT, never commits. Secondary:
`app/db/repositories/run_repo.py:55-71` (tolerant readers) and `:123-157` (frozen dataclass).

**House rules docstring** (`run_repo.py:227`):
```python
    """Every run, newest first, bounded by `limit`. Never commits (the caller owns it)."""
```

**Allow-list + keyword-only writer + SAVEPOINT** (`event_repo.py:148-185`):
```python
async def append_event(
    session: AsyncSession,
    *,
    listing_id: int,
    event_type: str,
    now: datetime,
    run_id: int | None = None,
    context: Mapping[str, Any] | None = None,
) -> ListingEvent:
    """Append exactly one event. The only write this module performs, and it is INSERT.
    ...
    The insert is wrapped in a SAVEPOINT as `source_repo` does: a failure here must not
    poison the caller's outer transaction. There is deliberately no update and no
    delete function in this module, and the Phase-1 triggers would refuse one anyway.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(
            f"unknown event_type {event_type!r}; expected one of {list(EVENT_TYPES)}"
        )

    event = ListingEvent(...)
    async with session.begin_nested():
        session.add(event)
        await session.flush()
    return event
```

**Frozen read value + explicit sentinel** (`event_repo.py:69-90`) — copy for `LlmCallRecord`:
```python
@dataclass(frozen=True)
class ListingState:
    """A listing's current state, projected from its events.

    A frozen value, never an ORM row: callers cannot mutate it back into the
    database, which is the point of projecting rather than storing.
    """
    ...
NO_STATE = ListingState()
```

**Tolerant JSON/None accessors** (`run_repo.py:55-71`) — `latest_probe` must default rather than
raise:
```python
def _mapping(value: Any) -> dict[str, Any]:
    """A JSON object column as a dict, or `{}` — never raises."""
    return dict(value) if isinstance(value, Mapping) else {}

def _int(value: Any) -> int:
    """An integer, or 0 for anything unusable (a half-written row is still renderable)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
```

**Required surface** (RESEARCH §Repository Shape):
```python
PURPOSES = frozenset({"rank", "narrate", "tailor", "extract", "probe"})   # mirrors ck_llm_calls_purpose
STATUSES = frozenset({"ok", "invalid", "timeout", "error"})              # mirrors ck_llm_calls_status

async def record_llm_call(session, *, purpose, status, result=None, backend=None,
                          provider=None, model=None, agent=None, server_version=None,
                          prompt_tokens=None, completion_tokens=None, latency_ms=None,
                          attempts=None, error=None, run_id=None, now=None) -> LlmCallRecord: ...
async def latest_probe(session) -> LlmCallRecord | None: ...
async def llm_totals_for_run(session, *, run_id) -> tuple[int, int]: ...
```

**Validation:** `purpose`/`status` validated against the frozensets in Python **before** the INSERT,
so an unknown value raises a clear `ValueError` rather than a raw `IntegrityError` (mirrors
`event_repo.py:170-173`). `run_id` defaults to `None` so the selftest cannot create a `runs` row (D-50).

---

### `alembic/versions/0003_llm_call_server_version.py` (NEW — migration)

**Analog:** `alembic/versions/0002_queue_filter_and_run_reason.py`

**Module docstring + revision header** (lines 1-48) — copy the header style exactly:
```python
"""queue filter rules, the last-visit watermark and the run-reason columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16
...
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None
```

**Additive nullable column** (lines 89-95) — 0003 is one column:
```python
    # `op.add_column` with a nullable column is a true in-place ALTER on SQLite.
    op.add_column("runs", sa.Column("reason", sa.String(32)))
```
→ `op.add_column("llm_calls", sa.Column("server_version", sa.String(32)))`, and the symmetric
`op.drop_column("llm_calls", "server_version")` in `downgrade()` (lines 117-134).

**Version bump required** (0003 with `revision = "0003"`, `down_revision = "0002"`,
`branch_labels = None`, `depends_on = None`).

**Guards tripped** (RESEARCH §The guards this deliberately trips):
- `tests/db/test_migration_contract.py:294` `assert versions == ["0002"]` → `["0003"]`
- `tests/db/test_migration_contract.py:305` `head_lines[0].startswith("0002")` → `"0003"`
- `tests/db/test_migration_contract.py:500` `assert versions == ["0002"]` → `["0003"]`
- plus the module docstring / comment headers at `:4, :26, :313, :370, :396, :440`
- `tests/db/test_orm_drift.py:81-103` needs **no edit** — it enforces the ORM mirror matches
- `tests/db/test_no_pii_columns.py:68` (`"llm_calls": frozenset()`) needs **no edit** — VARCHAR ≠ JSON

---

### `app/db/models.py` (ORM model, CRUD)

**Analog:** `app/db/models.py:440-469` (self)

**Add the ORM mirror** immediately after `agent` (line 451) / before `prompt_tokens`; note
`Run.llm_calls` / `Run.llm_tokens` / `Run.ranked_count` already exist (lines 293-296):
```python
    server_version = Column(String(32))     # D-12 / M9 — from GET /global/health

    __table_args__ = (
        CheckConstraint(
            "purpose IN ('rank','narrate','tailor','extract','probe')",
            name="ck_llm_calls_purpose",
        ),
        CheckConstraint(
            "status IN ('ok','invalid','timeout','error')",
            name="ck_llm_calls_status",
        ),
    )
```
`tests/db/test_orm_drift.py` asserts per-table **column-name equality** ORM ↔ migrated, so this
edit and migration 0003 must land together.

---

### `app/config.py` (Settings)

**Analog:** `app/config.py:30-37` (self)

**Settings model config** (lines 13-21) — unchanged:
```python
class Settings(BaseSettings):
    """Environment-driven settings. Every field has a safe default."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
```

**Existing opencode block** (lines 30-37) — note `opencode_timeout_seconds` is scoped to
health/discovery only; **do not reuse it for a completion** (P4):
```python
    # --- opencode backend (D-05..D-10) ---------------------------------------
    # The server is user-managed and external; the app never owns or pins it.
    opencode_base_url: str = "http://host.docker.internal:4096"
    opencode_model: str = "deepseek-v4.1-flash"
    opencode_server_password: str = ""
    #: Bounded timeout for the health/discovery calls (T-01-32): a hung request
    #: must not pin the single worker. Configuration, not a constant (PLAT-04).
    opencode_timeout_seconds: float = 5.0
```

**New fields** (RESEARCH §New Settings fields required) — every ceiling is a Settings field:
```python
    # --- opencode completion budget (Phase 3) ---------------------------------
    opencode_completion_timeout_seconds: float = 120.0
    opencode_max_retries: int = 2                 # client-side resends
    opencode_structured_retry_count: int = 2      # sent as format.retryCount
```

**Required companion edits:** `tests/test_config.py:28-44` (`REQUIRED_SETTINGS_FIELDS` +
`LIMIT_FIELDS`); `compose.yml:15-29` passthrough (or a host `.env` override silently loses);
`.env.example`.

---

### `app/api/settings.py` (route/handler, request-response)

**Analog:** `app/api/settings.py:110-119` (GET) and `:211-333` (plain-POST route) — extend in place.

**Route + templates + module constants** (lines 18-77):
```python
from app.api.deps import current_user
from app.db.session import get_session
from app.domain.models import User
from app.web.template_env import make_templates

router = APIRouter()
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
templates = make_templates(TEMPLATE_DIR)
SETTINGS_TEMPLATE = "html/settings.html"
RESET_CONFIRM_TOKEN = "DELETE"
```

**`_settings_context`** (lines 91-107) — extend this to include the latest probe row for D-52:
```python
async def _settings_context(
    session: AsyncSession,
    *,
    banner: str | None = None,
    error: bool = False,
) -> dict[str, Any]:
    ...
    return {
        "banner": banner,
        "error": error,
        "counts": await _counts(session),
        ...
    }
```

**Auth seam on every route** (lines 110-119, 211-216) — `POST /settings/llm-test` MUST declare
`Depends(current_user)` or `tests/test_auth_seam.py:87-98` fails:
```python
@router.post("/settings/reset", response_class=HTMLResponse)
async def reset_data(
    request: Request,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
```

**New route core pattern** (RESEARCH §Selftest Route + UI Surface "What it does") — plain
full-page POST (resolution (i)), route owns the commit:
```python
@router.post("/settings/llm-test", response_class=HTMLResponse)
async def test_llm_backend(request, user=Depends(current_user),
                           session=Depends(get_session),
                           backend: LLMBackend = Depends(get_llm_backend)):
    result = await backend.complete_structured(
        schema=ProbeResult,
        system=SELFTEST_SYSTEM_PROMPT,          # module-level CONSTANT, no interpolation
        parts=[SELFTEST_USER_PARTS],            # CANNED instruction-like snippet (D-51)
        model=settings.opencode_model, agent=None,
        tools=(), retries=settings.opencode_max_retries,
    )
    record = await llm_call_repo.record_llm_call(
        session, purpose="probe", status=result.status, result=result,
        server_version=result.server_version, run_id=None, now=now,
    )
    await session.commit()                      # the route owns the commit
    return templates.TemplateResponse(request, SETTINGS_TEMPLATE, await _settings_context(...))
```

**Error handling / guards** (lines 229-323) — refuse rather than improvise; render the honest
banner with the right status code; never let an exception become a bare 500.

**Test constraint:** `hx-post` anywhere on `/settings` fails
`tests/api/test_settings_page.py:54-59`. Use a plain `<form method="post" action="/settings/llm-test">`.

---

### `app/api/health.py` (route/handler — guard: do NOT change shape)

**Analog:** `app/api/health.py:40-112` (self) — read-only reference; no change expected this phase.

**Total-function report** (lines 40-50):
```python
async def _opencode_report(backend: LLMBackend) -> dict[str, Any]:
    """`{reachable, version, error}`. A backend bug must not break `/health`."""
    try:
        outcome = await backend.health()
    except Exception as exc:  # noqa: BLE001 — health is a total function
        return {"reachable": False, "version": None, "error": type(exc).__name__}
    return {
        "reachable": bool(outcome.reachable),
        "version": outcome.version,
        "error": outcome.error,
    }
```

**Shape is pinned exactly** (lines 106-112) — `tests/api/test_health.py:253-257` pins the `opencode`
dict keys and `:394` pins the top-level key set `{"status","db","opencode","sources"}`. **Adding
either a top-level key or an `opencode` key breaks the suite.** The selftest belongs on `/settings`.

---

### `app/api/deps.py` (auth seam)

**Analog:** `app/api/deps.py` (self) — every new route declares this; body unchanged:
```python
LOCAL_USER = User(id=settings.local_user_id, name="Local", email=None)


async def current_user() -> User:
    """v1: the single local user. Later: OIDC/Authentik via authlib.

    ROUTE SIGNATURES DO NOT CHANGE: the OIDC implementation replaces only the
    body of this function (ARCHITECTURE §11.1).
    """
    return LOCAL_USER
```

---

### `app/web/routes.py` (route/handler — optional badge only)

**Analog:** `app/web/routes.py:71-90` (`_health_strip`) — the existing "never 500 the product page"
pattern. Phase 3's only possible change here is the queue "flagged" badge plumbing (Q5); treat as
optional and check `tests/api/test_queue_{links,signals,dismiss}.py` first.
```python
async def _health_strip(
    session: AsyncSession, backend: LLMBackend
) -> tuple[list[SourceHealth], bool, str | None, str | None]:
    """`(rows, reachable, version, error)` — never raises, never probes a board."""
    try:
        rows = await get_source_health(session)
    except Exception as exc:  # noqa: BLE001 — decorative data must not 500 the page
        log.warning("queue.health_read_failed", error=type(exc).__name__)
        rows = []
    ...
```

---

### `app/pipeline/run.py` (pipeline seam, batch)

**Analog:** `app/pipeline/run.py:247-283` (`_persist_result`) and `:549-595` (`_finish`) — extend in place.

**Discarded sanitize report → stop discarding** (lines 263-275) — the exact gap §6.3 requires:
```python
    async with session_factory() as session:
        for raw in result.items:
            try:
                async with session.begin_nested():
                    sanitised, _report = await sanitize_listing(raw)
                    normalised = normalise_listing(sanitised)
                    outcome = await upsert_listing_source(
                        session,
                        source=result.source,
                        norm=normalised,
                        run_id=run_id,
                        now=now,
                    )
```
→ `sanitised, report = await sanitize_listing(raw)`, build `signals` from
`report.instruction_like` / `report.patterns_matched`, pass
`normalise_listing(sanitised, quality_signals=signals if (…) else None)`. The `else None` keeps a
clean listing's column NULL so `listing_repo`'s `if value is not None` (lines 123-126) never clobbers.

**`_finish()` writer seam** (lines 549-595) — add keyword params, assign only when not `None`; leave
`ranked_count` alone (Phase 5 owns it):
```python
async def _finish(
    session_factory: async_sessionmaker[AsyncSession],
    run_id: int,
    *,
    status: str,
    source_counts: dict[str, Any],
    errors: list[dict[str, Any]],
    merged_count: int = 0,
    filtered_count: int = 0,
    stage_log: list[dict[str, Any]] | None = None,
    reason: str | None = None,
    reason_counts: dict[str, Any] | None = None,
    llm_calls: int | None = None,      # NEW — Phase 3 seam
    llm_tokens: int | None = None,     # NEW — Phase 3 seam
) -> None:
    ...
        run.filtered_count = filtered_count
        run.stage_log_json = stage_log or None
        run.reason = reason
        run.reason_counts_json = reason_counts or None
        await session.commit()
```

**Hard constraint:** `tests/pipeline/test_filter_stage.py:197` asserts
`await _count(session_factory, LlmCall) == 0` after a filter run. **Shipping the seam is fine;
wiring a caller is not** (D-49). Prove the seam with a direct unit test.

---

### `app/pipeline/stages.py` (pipeline stage)

**Analog:** `app/pipeline/stages.py:60-115` (self) — add a keyword-only `quality_signals` argument;
keep the function pure (no DB/network).
```python
def normalise_listing(raw: RawListing) -> NormalisedListing:
    """Board-shaped `RawListing` -> canonical `NormalisedListing`.

    Pure: one function, no I/O, so both dedup keys are unit-testable without a
    database or a network (Pattern 2).
    """
```
→ `def normalise_listing(raw, *, quality_signals: Mapping[str, Any] | None = None)` and pass it
into `NormalisedListing(... quality_signals=...)` at line 114 (beside `source_extras`).

---

### `app/domain/models.py` (domain dataclass)

**Analog:** `app/domain/models.py:74-84` (self) — mirror the existing `source_extras` property
pattern exactly:
```python
    source_extras: dict = field(default_factory=dict)

    @property
    def remote_flag(self) -> bool | None:
        """The DB column name for `is_remote`."""
        return self.is_remote

    @property
    def source_extras_json(self) -> dict | None:
        """The DB column name for `source_extras`."""
        return self.source_extras or None
```
→ add `quality_signals: dict | None = None` + `quality_signals_json` property.

---

### `app/domain/sanitize.py` (read-only analog)

**Analog:** `app/domain/sanitize.py:96-125` (self) — **no change needed**; `SanitizeReport` already
carries `instruction_like` / `patterns_matched`, and the counts-only property is the invariant:
```python
@dataclass(frozen=True)
class SanitizeReport:
    """What was removed/changed. Counts only — never the removed value."""
    ...
    instruction_like: bool = False
    #: How many `INJECTION_PATTERNS` matched the sanitised text (D-38). A count
    #: only — deliberately no field can carry the matched text.
    patterns_matched: int = 0
```

---

### `app/db/repositories/listing_repo.py` (read-only analog)

**Analog:** `app/db/repositories/listing_repo.py:37-60, 123-126` (self) — no change; the
nullable-guard is why `quality_signals_json` is the right home:
```python
_LISTING_FIELDS = (
    ...
    "quality_signals_json",
    "source_extras_json",
    "blocking_key",
)
...
        for field in _LISTING_FIELDS:
            value = _value(norm, field)
            if value is not None:
                setattr(row, field, value)
```

---

### `app/web/templates/html/settings.html` (template)

**Analog:** `app/web/templates/html/settings.html` (self) — add a "Test LLM backend" `<section>`
before the danger card, using the same card/banner/plain-form idioms:
```jinja
{% if banner %}
<p class="settings-banner{% if error %} settings-banner-error{% endif %}" id="settings-banner">{{ banner }}</p>
{% endif %}

<section class="settings-card">
  <h3>Queue data</h3>
  ...
</section>

<section class="danger-card" id="danger-zone">
  ...
  <form method="post" action="/settings/reset">
```
New section: `<form method="post" action="/settings/llm-test">` with a submit button; render D-52's
`status`, `error_kind`, `attempts`, `latency_ms`, validation message, and the constant system prompt.

---

### `app/web/templates/html/_llm_test_result.html` (NEW, optional partial)

**Analog:** `app/web/templates/html/_run_status.html` — the repo's HTML-fragment convention. Use
`make_templates` (`app/web/template_env.py:11-17`):
```python
def make_templates(directory: str | Path) -> Jinja2Templates:
    """A ``Jinja2Templates`` instance with the application's filters registered."""
    templates = Jinja2Templates(directory=str(directory))
    templates.env.filters["human_label"] = filters.human_label
    templates.env.filters["format_datetime"] = filters.format_datetime
    return templates
```

---

## Test Pattern Assignments

### `tests/llm/fixtures/opencode-doc.json` (NEW fixture)

**Analog:** `tests/fixtures/opencode_providers.json` — committed JSON under a `fixtures/` dir.
Phase 3 creates `tests/llm/fixtures/` (dir does not exist yet).
Shape per RESEARCH §Pinning Strategy B: a **hand-written projection** (`_meta` + `paths` +
`components.schemas`) keeping only the structured-output slice. Not a full `/doc` dump (D-55).

### `tests/llm/test_contract_snapshot.py` (NEW — default lane)

**Analog:** `tests/llm/test_discovery_redaction.py` (import style, asserts on module source) +
`tests/test_import_discipline.py:37-53` and `tests/test_config.py:191-203` for "a guard that cannot
fail is not a guard".
```python
def test_the_walker_actually_detects_a_forbidden_import() -> None:
    """A guard that cannot fail is not a guard."""
    offenders = _imported_top_level_modules(
        "import httpx\nfrom sqlalchemy import select\n"
    )
    assert offenders & FORBIDDEN_TOP_LEVEL_MODULES == {"httpx", "sqlalchemy"}
```
Assertions per RESEARCH §Pinning Strategy C: builder == constants; constants ∈ snapshot;
negative control (`"outputFormat"`, `"structured_output"` absent); request-builder model shape.

### `tests/llm/test_contract_live.py` (NEW — live lane)

**Analog:** `tests/live/test_probe_live.py`
```python
pytestmark = pytest.mark.live
```
Docstring must state the lane and the operator command (lines 1-18). Live test is **spec fetch +
diff only** (D-57) — no LLM call. Marker declared in `pyproject.toml:49-58`
(`addopts = "-m 'not live'"`).

### `tests/llm/test_complete_structured.py` (NEW — unit)

**Analog:** `tests/llm/test_discovery_redaction.py:53-91` — the `Recorder` fake-`httpx` module
monkeypatched in, recording paths and client kwargs; **nothing touches the network**:
```python
class Recorder:
    """A fake `httpx` module for `app.llm.opencode_server`, recording request paths."""
    def __init__(self) -> None:
        self.paths: list[str] = []
        self.client_kwargs: list[dict[str, Any]] = []
    def module(self, *, status_code=200, body=None, error=None, json_error=None):
        ...
        class FakeClient:
            async def __aenter__(self): return self
            async def __aexit__(self, *exc): return False
            async def get(self, url): ...
        return types.SimpleNamespace(AsyncClient=FakeClient, BasicAuth=httpx.BasicAuth)
```
Cover (RESEARCH Phase Requirements → Test Map): ok / invalid (`StructuredOutputError` → `attempts`
from `data.retries`) / timeout / unreachable; the bounded retry loop; identity recording.

### `tests/llm/test_salvage.py` (NEW — unit)

**Analog:** `tests/llm/test_discovery_redaction.py` (parametrized malformed payloads at lines
155-161). Cover `from_json(allow_partial=True)` + the tolerated-error allow-list + the
`PydanticUseDefault`-on-a-defaultless-field pitfall (P11).

### `tests/llm/test_trust_boundary.py` (NEW — guard)

**Analog:** `tests/test_import_discipline.py:14-18` (AST/structural guard) +
`tests/domain/test_injection_patterns.py`. Assert: untrusted text cannot reach `system`; `tools`
deny encoding; the system prompt is a module constant (criterion 4). Add a "guard can fail" companion.

### `tests/api/test_llm_selftest.py` (NEW — integration)

**Analog:** `tests/api/test_settings_page.py` (route/HTML assertions) and
`tests/api/test_settings_reset.py:144` (`LlmCall(...)` seeding). Use the `client` fixture
(`tests/conftest.py:238-266`) which overrides `get_llm_backend` with `OfflineLLMBackend`. Assert:
one call → one `llm_calls` row with `run_id IS NULL`, `purpose='probe'`; **no** `runs` row; D-52's
rendered detail (status, attempts, latency, validation message), not a bare badge.

### `tests/db/test_llm_call_repo.py` (NEW — integration)

**Analog:** `tests/db/test_search_repo_writes.py` / `tests/db/test_listing_events.py` (uses
`session_factory`/`db_session` fixtures). Assert: `now` pinning, never-commits, `purpose`/`status`
validation raises `ValueError`, `server_version` round-trips.

### `tests/pipeline/test_injection_finding.py` (NEW — integration)

**Analog:** `tests/pipeline/test_filter_stage.py` — same run harness. Assert the flag lands on
`listings.quality_signals_json` and a clean listing leaves it NULL.

### `tests/llm/test_discovery_redaction.py` (MODIFY)

**Analog:** self. **Two edits:**
1. `tests/fixtures/opencode_providers.json` — its `models` is a **list** and its credential field is
   **`api_key`**; live 1.18.31 uses a **dict** and **`key`** (P1). Update the field name so the guard
   isn't testing a fiction; keep `SENTINEL` (line 43) and the non-vacuity assertion (line 195).
2. Add a live-dict-shape test asserting the expected `ProviderModel` pairs.
Keep the sentinel scans (lines 192-253) and the `vars(backend)` assertion (line 235).

### `tests/conftest.py` (MODIFY)

**Analog:** self:33-45. `OfflineLLMBackend` must gain `complete_structured` (P10) or the selftest
route `AttributeError`s in the default lane:
```python
class OfflineLLMBackend:
    """Stands in for `OpenCodeServerBackend` without touching the network."""
    async def health(self) -> ProbeOutcome:
        return ProbeOutcome(reachable=False, error="offline-test-lane")
    async def discover_models(self) -> DiscoveryResult:
        return DiscoveryResult(reachable=False, error="offline-test-lane")
```
→ add `async def complete_structured(self, **kwargs) -> StructuredCallResult: return
StructuredCallResult(ok=False, status="error", error="offline-test-lane")`.

### `tests/test_auth_seam.py` (MODIFY)

**Analog:** self:28-31 (subset assertion — update recommended but not required):
```python
EXPECTED_SEAM_ROUTES = frozenset({"/", "/runs", "/runs/{run_id}/status", "/health"})
```
→ add `"/settings/llm-test"` (and `"/settings"`, `"/settings/reset"` if being thorough). The walk at
`:87-98` auto-covers new routes; the set only makes non-vacuity explicit.

### `tests/test_config.py` (MODIFY)

**Analog:** self:28-59. Add the new ceilings to both tuples:
```python
REQUIRED_SETTINGS_FIELDS = ( ..., "opencode_max_retries", "opencode_completion_timeout_seconds", ... )
LIMIT_FIELDS = ( ..., "opencode_max_retries", ... )
```
The AST absence scan (`SCANNED_DIRS = ("app/probe", "app/pipeline")`, lines 156-188) will fail if a
distinctive new ceiling literal appears in the pipeline.

### `tests/api/test_settings_page.py` (MODIFY only if HTMX chosen)

**Analog:** self:54-59. With the recommended plain-POST resolution this file needs **no change**:
```python
def test_the_reset_form_is_a_plain_post_and_not_an_htmx_swap(client) -> None:
    """A destructive action is a full navigation; a partial swap gains nothing."""
    response = await client.get("/settings")
    assert '<form method="post" action="/settings/reset">' in response.text
    assert "hx-post" not in response.text
```

### `tests/db/test_migration_contract.py` (MODIFY)

**Analog:** self:294, 305, 500 — bump `["0002"]` → `["0003"]` and `startswith("0002")` →
`startswith("0003")`; extend the docstring/comment headers at `:4, :26, :313, :370, :396, :440`.

### `tests/api/test_health.py` (MODIFY? — guard only)

**Analog:** self:253-257, 394. **No change intended**; keep it green as the "shape unchanged" proof.

### `tests/test_import_discipline.py` (MODIFY)

**Analog:** self:14-18, 64-82. Extend the guard to the LLM call path (`app/pipeline`, `app/api`,
`app/web`, `app/probe`) — **but scope it** (P6): `app/sources/linkedin.py:13` and
`app/sources/indeed.py:21` legitimately import `httpx`, so a blanket all-of-`app/` guard fails on
day one. `subprocess` can be asserted globally outside `app/llm`.
```python
FORBIDDEN_TOP_LEVEL_MODULES = frozenset(
    {"httpx", "sqlalchemy", "jobspy", "jinja2", "subprocess", "fastapi"}
)
```

### `tests/fixtures/opencode_providers.json` (MODIFY)

**Analog:** self — change `models` list → dict and `api_key` → `key` (or add a second fixture in the
live shape). Keep the `SENTINEL-PROVIDER-CREDENTIAL-DO-NOT-LOG` string.

### Docs: `docs/runbook-opencode-contract.md` (NEW) or `docs/runbook-compose-smoke.md` (MODIFY)

**Analog:** `docs/runbook-compose-smoke.md` + `docs/probes/README.md`. Add D-53's four-step
operator procedure (default lane → source `.env` → live lane → refresh fixture deliberately),
plus the `host.docker.internal` vs `127.0.0.1` note and the `--hostname 0.0.0.0` precondition.

### `.env.example` (MODIFY) / `compose.yml` (MODIFY)

**Analog:** self. Add the new `OPENCODE_*` keys to `.env.example` and to `compose.yml:15-29`'s
`environment:` passthrough list (the comment at lines 21-25 documents why: an unforwarded host
`.env` silently loses to the in-code default).

---

## Shared Patterns

### Auth seam (every route)
**Source:** `app/api/deps.py:14-22` + `app/api/settings.py:211-216`
**Apply to:** `POST /settings/llm-test` (and any new route)
```python
async def current_user() -> User:
    """v1: the single local user. Later: OIDC/Authentik via authlib.

    ROUTE SIGNATURES DO NOT CHANGE: the OIDC implementation replaces only the
    body of this function (ARCHITECTURE §11.1).
    """
    return LOCAL_USER
```
Enforced by `tests/test_auth_seam.py:87-98` (walks every leaf route with a `Dependant`).

### Redaction as a type property (never persist/log/cache raw)
**Source:** `app/llm/base.py:21-32`, `app/llm/opencode_server.py:141-147`
**Apply to:** `StructuredCallResult`, `parse_providers`, `ProbeResult`, `record_llm_call`, any log line
```python
model_config = ConfigDict(extra="forbid")   # a raw entry with a secret raises, not drops
```
`raw` stays **in-memory only**; `llm_calls` has **zero JSON columns**
(`tests/db/test_no_pii_columns.py:68`). Never assign a response body to `self`, never log it, never
cache it, never persist it. The sentinel scan pattern is `tests/llm/test_discovery_redaction.py:192-253`.

### Total functions / failure-as-value
**Source:** `app/llm/opencode_server.py:109-155`, `app/api/health.py:40-50`, `app/web/routes.py:71-90`
**Apply to:** `complete_structured`, `record_llm_call` read helpers, the selftest route
```python
except Exception as exc:  # noqa: BLE001 — boot tolerance
    return ProbeOutcome(reachable=False, error=type(exc).__name__)
```
`/health` always HTTP 200; `docker compose up` must never depend on opencode (D-08); a validation
failure is a **run outcome** (`status='invalid'`), never a crash.

### Repository / transaction
**Source:** `app/db/repositories/event_repo.py:148-185`, `app/db/repositories/run_repo.py:227`
**Apply to:** `llm_call_repo.record_llm_call`
- `session: AsyncSession` first, then `*`, then entity fields, plus `now: datetime | None = None`
- validate enums against frozensets before the INSERT
- wrap the INSERT in `session.begin_nested()` (SAVEPOINT)
- **never commit** — the caller owns the single `commit()`
- return the ORM row or a frozen dataclass so the route renders from what was written

### Settings ceilings
**Source:** `app/config.py:30-37`, `tests/test_config.py:156-203`
**Apply to:** `opencode_completion_timeout_seconds`, `opencode_max_retries`,
`opencode_structured_retry_count`
Every numeric ceiling is a `Settings` field with a documented default — never a literal in
`app/pipeline` or `app/probe` (PLAT-04 AST scan). Forward each new key through `compose.yml` and
document it in `.env.example`, or a host override silently loses.

### Trust boundary / prompt injection
**Source:** `app/domain/sanitize.py:96-125`, ARCHITECTURE §6.3
**Apply to:** the selftest route's prompt assembly
Untrusted content goes in `parts` (user turn) **never** `system`; `tools` defaults to empty/deny;
`llm/` exposes no `system`-from-data path; the system prompt is a module-level constant with no
interpolation; instruction-like text is a **finding to record** (`quality_signals_json`), never
executed and never silently stripped.

### Guard-can-fail companion
**Source:** `tests/test_import_discipline.py:37-43`, `tests/test_config.py:191-203`,
`tests/test_auth_seam.py:107-121`
**Apply to:** every new guard (snapshot contract, trust boundary, import discipline, selftest)
Every new guard needs a companion test proving it can actually fail.

---

## No Analog Found

Files with no close match in the codebase (planner should use RESEARCH.md patterns instead):

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `app/llm/contract.py` | config/constants | transform (pure) | No existing pure-constants module; nearest is the path-constant pair in `opencode_server.py:29-30` — pattern transferred, not copied. |
| `tests/llm/fixtures/opencode-doc.json` | test fixture | — | No committed OpenAPI projection fixture exists; nearest is `tests/fixtures/opencode_providers.json` (a raw payload, not a projection). |
| `tests/llm/test_contract_snapshot.py` | test (unit/guard) | — | No snapshot-vs-builder contract test exists; composed from the `test_discovery_redaction` style + the guard-can-fail convention. |
| `tests/llm/test_contract_live.py` | test (live lane) | — | Live pattern exists (`tests/live/test_probe_live.py`) but no live *contract-diff* test; transfer the marker + docstring convention. |

---

## Metadata

**Analog search scope:** `app/llm/`, `app/db/repositories/`, `app/db/models.py`, `app/api/`,
`app/web/`, `app/pipeline/`, `app/domain/`, `alembic/versions/`, `tests/llm/`, `tests/api/`,
`tests/db/`, `tests/pipeline/`, `tests/live/`, `tests/fixtures/`, `docs/`, `compose.yml`,
`.env.example`, `pyproject.toml`
**Files scanned:** 31 analog files read directly (plus the phase's CONTEXT.md and targeted
RESEARCH.md windows)
**Pattern extraction date:** 2026-09-17
**Tracked-source gate:** all 31 analog paths verified tracked via `git ls-files -- <path>`;
no gitignored mirror paths emitted.
