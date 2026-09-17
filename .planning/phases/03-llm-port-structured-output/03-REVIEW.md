---
phase: 03-llm-port-structured-output
reviewed: 2026-09-17T23:37:37Z
depth: standard
files_reviewed: 41
files_reviewed_list:
  - .env.example
  - alembic/versions/0003_llm_call_server_version.py
  - app/api/settings.py
  - app/config.py
  - app/db/models.py
  - app/db/repositories/llm_call_repo.py
  - app/db/repositories/queue_repo.py
  - app/domain/models.py
  - app/domain/schemas/__init__.py
  - app/domain/schemas/probe.py
  - app/llm/__init__.py
  - app/llm/base.py
  - app/llm/builders.py
  - app/llm/contract.py
  - app/llm/opencode_server.py
  - app/pipeline/run.py
  - app/pipeline/stages.py
  - app/web/templates/html/_listing_row.html
  - app/web/templates/html/settings.html
  - compose.yml
  - docs/runbook-opencode-contract.md
  - static/vendor/app.css
  - tests/api/test_health.py
  - tests/api/test_llm_selftest.py
  - tests/conftest.py
  - tests/db/test_llm_call_repo.py
  - tests/db/test_migration_contract.py
  - tests/db/test_skeleton_boot.py
  - tests/fixtures/opencode_providers.json
  - tests/llm/fixtures/opencode-doc.json
  - tests/llm/test_complete_structured.py
  - tests/llm/test_contract_live.py
  - tests/llm/test_contract_snapshot.py
  - tests/llm/test_discovery_redaction.py
  - tests/llm/test_salvage.py
  - tests/llm/test_trust_boundary.py
  - tests/pipeline/test_finish_llm_counters.py
  - tests/pipeline/test_injection_finding.py
  - tests/test_auth_seam.py
  - tests/test_config.py
  - tests/test_import_discipline.py
findings:
  critical: 0
  warning: 4
  info: 6
  total: 10
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-09-17T23:37:37Z
**Depth:** standard
**Files Reviewed:** 41
**Status:** issues_found

## Summary

Phase 3 lands a well-structured port/adapter split: `complete_structured` is total by
construction (failure-as-value), the wire vocabulary is centralised in `app/llm/contract.py`,
untrusted text is confined to `parts`, the single production `system` value is a module
constant, and the discovery path copies identifiers only. The migration/model pair for
`llm_calls.server_version` is in sync (`sa.String(32)` nullable in both), the `_finish` seam
preserves omitted counters, and the secret sentinel is provably absent from logs, the DB and
the page. Baseline suite corroborated: **826 passed / 3 deselected**.

Four Warning-level defects remain, all in the adapter/error-classification path and in the
contract test's coverage of the tool-deny control:

1. `complete_structured` accepts a `tools` allow-list and **silently drops it** — the
   parameter never reaches `to_message_body`, and its type does not even match the builder's.
   The only `tools` tests call the builder directly, so the end-to-end forwarding is untested.
2. The `retries` parameter's literal default of `2` makes the documented
   `settings.opencode_max_retries` fallback **unreachable**, so a caller that omits `retries`
   ignores the configured ceiling (PLAT-04). Demonstrated: with `opencode_max_retries = 7`,
   an omitted `retries` still issues exactly 2 attempts.
3. A malformed (non-parseable) `info.structured` string raises `ValueError` from
   `from_json(allow_partial=True)`, escaping `_salvage`'s `except ValidationError`, and is
   reclassified by the outer generic handler as `status="error"`, `error_kind="ValueError"`,
   `attempts=0`, with `provider`/`model`/`agent`/`part_types`/`info_keys` all nulled. A model
   output defect should be `invalid` and should preserve the identity/observation already
   parsed from the response.
4. The tool-deny wire shape (`{permission, pattern, action}` / `action: "deny"`) has **no
   contract test** — it is absent from the `/doc` fixture, not asserted by the default-lane
   snapshot test, and not projected by the live lane. Only the session property *name*
   `permission` is covered (by the live lane's name-set diff). A server-side rename of the
   rule's inner fields would silently turn the enforced deny into a no-op.

No Critical findings: no injection, credential leak, auth bypass, unbounded call ceiling, or
raise-leak from the port was found. The reset-route CSRF discussion in `app/api/settings.py`
is pre-existing (the Phase-3 diff adds only the LLM selftest route and its context) and is
deliberately documented; it is not reported here.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: `complete_structured` accepts `tools` and silently discards it

**File:** `app/llm/opencode_server.py:355` (parameter) and `:413-423` (body construction);
see also `app/llm/base.py:121` and `app/llm/builders.py:64`

**Issue:** The port (`LLMBackend.complete_structured`), the concrete adapter, and the method
docstring all advertise an explicit per-name tool allow-list:

> `tools` is accepted for the port contract (default empty = no message-level grant); an
> explicit allow-list is emitted as a name→boolean map …

but the `to_message_body(...)` call never passes `tools=`, so the argument is dead. Verified
in-process: calling `complete_structured(..., tools=("read", "bash"))` produces a message body
with keys `['format', 'model', 'parts', 'system']` and no `tools` key. There is also a type
contract mismatch — the port declares `tools: Sequence[str]`, while the builder expects
`Mapping[str, bool]`, so a naive `tools=tools` "fix" would build the wrong wire shape. The only
tests of `tools` (`tests/llm/test_trust_boundary.py:53-78`) call `to_message_body` directly, so
the adapter-level forwarding has no test at all.

Today this fails closed (the session `permission` deny is the enforced control), but a Phase 5
caller passing an explicit grant gets a silent no-op and no diagnostic.

**Fix:** Convert at the adapter boundary and forward it:

```python
body = to_message_body(
    schema=schema,
    system=system,
    parts=parts,
    provider_id=provider_id,
    model_id=model_id,
    agent=agent,
    retry_count=settings.opencode_structured_retry_count,
    # An explicit per-name grant; empty stays absent (the session deny is the control).
    tools={name: True for name in tools} if tools else None,
)
```

Add a companion test that asserts the key is (and stays) absent when `tools=()` and present
when `tools=("read",)` via `complete_structured` (not `to_message_body`).

### WR-02: `retries` literal default bypasses `settings.opencode_max_retries`

**File:** `app/llm/opencode_server.py:356` and `:402-403`

**Issue:** The parameter is declared `retries: int = 2`, and the budget line is:

```python
budget = retries if retries is not None else settings.opencode_max_retries
```

Because `retries` can never be `None` when omitted (it defaults to the literal `2`, and the
annotation forbids `None`), the `settings.opencode_max_retries` branch is unreachable for any
caller that omits the argument. The surrounding comment and the method docstring claim the
opposite ("whose default is `settings.opencode_max_retries`"; "`Settings` supplies only the
DEFAULT"). Verified: with `settings.opencode_max_retries = 7`, an omitted `retries` still
issues exactly 2 message POSTs and reports `attempts == 2`. The shipped route happens to pass
`settings.opencode_max_retries` explicitly, which masks the defect; this is a PLAT-04 ("limits
are config, not constants") violation waiting for the next caller.

**Fix:** Make the default express the config, or make the fallback reachable:

```python
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
```

and keep `budget = retries if retries is not None else settings.opencode_max_retries`.

### WR-03: a non-parseable `info.structured` string is misclassified and loses the audit identity

**File:** `app/llm/opencode_server.py:792-810` (the `except ValidationError`), `:519-526`
(the generic handler), `:566-574` / `:598-647` (`_salvage`)

**Issue:** `_salvage` calls `pydantic_core.from_json(payload, allow_partial=True)`. `allow_partial`
tolerates a *truncated* tail, but it raises `ValueError` (not `ValidationError`) for input that
is not JSON at all — e.g. `"not json"` → `ValueError: expected ident at line 1 column 2`.
`_classify_message_response` only catches `ValidationError`, so the `ValueError` escapes that
method, propagates to the generic `except Exception` in `complete_structured`, and is rebuilt as
a *fresh* failure with none of the data already parsed from the 200 response. Reproduced with a
stub server returning `info.structured = "not json at all"`:

```
ok: False  status: error  error_kind: ValueError
attempts: 0  provider: None  model: None  agent: None
part_types: None  info_keys: None
```

Consequences: (a) a model-output defect is labelled a transport-class `error` instead of
`invalid`, weakening the four-value taxonomy (D-52) that success criterion 2 relies on;
(b) `attempts` is reported as `0` instead of the real issued count; (c) the D-12 identity
(`provider`/`model`/`agent`) — the entire reason migration 0003 exists — is nulled even though
`info.providerID`/`modelID`/`agent` were present and already parsed; (d) the trust-boundary
observation (`part_types`, `info_keys`) captured moments earlier is discarded. No test covers a
non-parseable structured string; `tests/llm/test_salvage.py` only covers a *parseable* truncated
string. The same over-broad `except Exception` also converts genuine programming errors (e.g. a
`TypeError` inside `_part_types`) into `error_kind=<ExceptionClassName>` rather than surfacing
them.

**Fix:** classify the salvage failure as an invalid output and preserve the parsed identity and
observation:

```python
try:
    data = _salvage(schema, structured)
except (ValidationError, ValueError) as exc:
    detail = exc.errors()[0].get("msg") if isinstance(exc, ValidationError) and exc.errors() else str(exc)
    return _failure(
        status="invalid",
        error_kind=ERROR_KIND_INVALID,
        error=f"validation failed: {detail}" if detail else "validation failed",
        attempts=attempts,
        started=started,
        server_version=server_version,
        part_types=part_types,
        info_keys=info_keys,
        **identity,
    )
```

and add a companion test with `structured="not json"` asserting `status == "invalid"`, the
provider/model survive, and `raw is None`.

### WR-04: the tool-deny rule shape is not covered by the contract test

**File:** `app/llm/contract.py:82-88`, `tests/llm/fixtures/opencode-doc.json`,
`tests/llm/test_contract_snapshot.py:131-137`, `tests/llm/test_contract_live.py` (no
`permission` reference)

**Issue:** Success criterion 4's enforced control is the session-level `permission` ruleset with
the fixed shape `{permission, pattern, action}` and `action == "deny"`. The committed `/doc`
snapshot lists `permission` as a session request property name but contains **no
`PermissionRule` schema**, `test_the_session_contract_matches_the_snapshot` does not assert
`permission` membership, and `_live_facts`/`_committed_facts` project no rule fields. So:
`PERMISSION_RULE_FIELDS` and `PERMISSION_DENY_ACTION` are pinned only by constants asserting
themselves (`tests/llm/test_trust_boundary.py:114-134`). If opencode renames the rule's fields
or the `deny` action value, every default-lane test stays green and the live lane reports no
diff, while `_create_session` keeps sending a ruleset the server may accept-but-ignore — i.e.
tools silently re-enabled on a listing-driven session. The phase deliberately built this test
machinery for exactly this class of rename (`format` vs `outputFormat`); the deny control
(the security-critical half) is not inside it.

**Fix:** Add a `PermissionRule` slice to `tests/llm/fixtures/opencode-doc.json`
(`properties`, `required`, `action_enum`), assert it in `test_contract_snapshot.py`
(`set(contract.PERMISSION_RULE_FIELDS) == required`, `contract.PERMISSION_DENY_ACTION in
action_enum`), add the matching projection to `_live_facts`/`_committed_facts` in
`test_contract_live.py`, and add a guard-can-fail companion using a deliberately wrong action
value.

## Info

### IN-01: the guard-can-fail companion exercises a helper the real assertions do not use

**File:** `tests/llm/test_contract_snapshot.py:62-80` vs `:113-119`, `:142-158`

**Issue:** `_missing_pointers` carries the docstring "One reusable helper so the guard-can-fail
companion exercises the SAME code path the real assertion uses", but
`test_the_request_side_contract_matches_the_snapshot` and
`test_the_response_side_contract_matches_the_snapshot` use inline membership assertions. Only
`test_the_pointer_check_can_actually_fail` calls the helper, so the companion proves the helper
has teeth while giving no evidence that the real assertions do.

**Fix:** Route the real assertions through `_missing_pointers(...) == []` so one code path is
genuinely shared, or delete the helper and rewrite the companion against the inline assertion.

### IN-02: `ProbeResult` docstring describes a salvage mechanism the code does not use

**File:** `app/domain/schemas/probe.py:11-13`

**Issue:** The docstring states "plan 03-03's salvage path uses `PydanticUseDefault`". The
implementation (`opencode_server._tolerant_validator`) never constructs `PydanticUseDefault`; it
drops tolerated top-level fields from a copy and re-validates. The "every field must declare a
default" requirement is still load-bearing (a default-less tolerated field re-raises), but the
stated mechanism is wrong and will mislead a future contributor. `PydanticUseDefault` appears
only in test code (`tests/llm/test_salvage.py`).

**Fix:** Reword to describe the drop-and-revalidate behaviour, keeping the reason all fields
declare defaults.

### IN-03: the "clean re-observation must not clobber a recorded signal" guard has no update-path test

**File:** `app/db/repositories/listing_repo.py:112-126`,
`tests/pipeline/test_injection_finding.py:157-189`

**Issue:** The entire `None`-not-`{}` design of `quality_signals` exists so that a clean
re-observation does not erase a previously recorded instruction-like finding (T-3-21). The
guard is the `if value is not None: setattr(...)` loop on the **update** branch
(`listing_repo.py:123-126`). Every persistence test in `test_injection_finding.py` exercises a
first-time insert; no test re-runs the pipeline over an already-flagged listing with a clean
payload and asserts the signal survives. A regression on the update path would be caught by no
test.

**Fix:** Add a test that runs once with instruction-like text, runs again with a clean
description for the same canonical URL, and asserts `listings.quality_signals_json` still holds
the original finding.

### IN-04: outer exception handlers report `attempts=0` and drop the already-known identity

**File:** `app/llm/opencode_server.py:499-526`; also `:706-714`

**Issue:** The outer `except httpx.TimeoutException` / `except httpx.TransportError` handlers
hard-code `attempts=0` and pass no `provider`/`model`/`agent`/`part_types`/`info_keys`, even
when the failure occurred *after* `_resolve_model` succeeded (the realistic path is a transport
failure during `_create_session`, which is outside the per-attempt retry loop). The recorded
audit row therefore understates the attempt count and loses the resolved identity. Separately,
the "response carried no info object" branch at `:706-714` passes `server_version` and
`part_types` but not the resolved `provider_id`/`model_id`.

**Fix:** Pass `attempts=issued`, and the resolved `provider=provider_id, model=model_id,
agent=agent` in the outer handlers; add `provider`/`model`/`agent` to the no-info-object branch.

### IN-05: a backend that raises produces no `llm_calls` row and a 200 response

**File:** `app/api/settings.py:404-424`

**Issue:** The route's defensive `except Exception` returns the settings page with HTTP 200 and
writes no audit row. `complete_structured` is total by contract, so this is defensive — but if a
future backend implementation does raise (e.g. a new adapter or a dependency change), a
token-spending attempt leaves no cost/audit trace, and the 200 hides the failure from anything
watching status codes. This path has no test. The reset route in the same file uses 400/409/500
for its refusals, so the convention is also inconsistent.

**Fix:** Return a non-200 status (e.g. 502) on the raised path and record an `error` row with
`error_kind=type(exc).__name__` so an attempted call is still auditable; add a test that
monkeypatches `complete_structured` to raise.

### IN-06: the non-200 body excerpt is persisted into `llm_calls.error` without redaction

**File:** `app/llm/opencode_server.py:566-574` and `:670-682`

**Issue:** `_bounded_excerpt` takes up to 200 characters of the non-200 response body and puts
it in `result.error`, which `llm_call_repo.record_llm_call` persists to the `llm_calls.error`
column and `settings.html:55` renders. The docstring calls it "a diagnostic, not a copy", but a
server/proxy error page (or a 4xx that echoes the request body) can carry arbitrary text. For
Phase 3's canned selftest body this is harmless; once Phase 5 sends CV text and listing bodies,
an echoing 4xx could persist a fragment of CV/listing content into an audit column that
`tests/db/test_no_pii_columns.py` treats as non-JSON but not as PII-safe.

**Fix:** Before the LLM path carries real CV data, either drop the body excerpt entirely, or
sanitise/cap it to a fixed set of safe fields (status line only), and document the decision in
the same place `NON_200_BODY_EXCERPT_CHARS` lives.

---

## Verified clean (selected focus areas)

- **Migration/model drift:** `alembic/versions/0003_llm_call_server_version.py:39` adds nullable
  `sa.String(32)`; `app/db/models.py:455` mirrors it as `Column(String(32))`. Item 14 of
  `tests/db/test_migration_contract.py` introspects the migrated DB, not the ORM, so drift fails
  loudly. Downgrade is symmetric.
- **Credential redaction:** `parse_providers` copies identifier keys only; `ProviderModel` is
  `extra="forbid"`; the raw discovery body is never logged, cached or attached; the sentinel
  tests cover structlog, caplog, stdout and every DB table.
- **`raw` response body:** never persisted, never logged; every failure branch sets `raw=None`;
  `StructuredCallResult` is `extra="forbid"`.
- **Prompt boundary:** `SELFTEST_SYSTEM_PROMPT` is an AST-verified single `Constant`; the
  builder emits `system` as a bare `Name`; untrusted content only enters `parts`.
- **`_finish` seam:** omitted counters preserve recorded values; `ranked_count` untouched;
  `run_pipeline()` still writes zero `llm_calls` rows (D-49 holds).
- **Bound parameters:** no SQL string interpolation in any repository changed here.

---

_Reviewed: 2026-09-17T23:37:37Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
