---
phase: 03-llm-port-structured-output
reviewed: 2026-09-18T10:54:12Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - app/api/settings.py
  - app/domain/schemas/probe.py
  - app/llm/base.py
  - app/llm/opencode_server.py
  - tests/api/test_llm_selftest.py
  - tests/llm/fixtures/opencode-doc.json
  - tests/llm/test_complete_structured.py
  - tests/llm/test_contract_live.py
  - tests/llm/test_contract_snapshot.py
  - tests/llm/test_trust_boundary.py
  - tests/pipeline/test_injection_finding.py
findings:
  critical: 0
  blocker: 0
  warning: 2
  info: 4
  total: 6
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-09-18T10:54:12Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

This is the narrowed re-review of gap-closure plans 03-08 and 03-09 (11 files changed
since `bf3d4e1`). The four prior Warnings and the prior Info-05 are genuinely closed, and
the closure is backed by tests that were executed, not just asserted in prose:

- **WR-01 (tools silently dropped) — CLOSED.** `complete_structured` now converts the port's
  `Sequence[str]` to `{name: True}` and forwards it (`opencode_server.py:420,428`). Verified
  end-to-end: `tools=("read","bash")` emits `{"read": True, "bash": True}`; an omitted/empty
  `tools` emits no key. Covered by the two new tests in `test_trust_boundary.py`.
- **WR-02 (retry ceiling literal) — CLOSED.** Both the Protocol (`base.py:122`) and the
  adapter (`opencode_server.py:356`) declare `retries: int | None = None`; the
  `settings.opencode_max_retries` fallback is now the live path. Verified: patching the
  setting to 7 yields exactly 7 completion POSTs and `attempts == 7`.
- **WR-03 (non-parseable payload misclassified) — CLOSED.** The new `except ValueError`
  branch (`opencode_server.py:820-842`) classifies non-JSON `info.structured` as
  `invalid`/`invalid` with the per-call identity and the trust-boundary observation intact.
  Verified in-process: `structured="not json at all"` → `invalid`, `attempts=1`,
  `provider`/`model`/`agent`/`part_types`/`info_keys` preserved. The branch is correctly
  ordered after `except ValidationError` (`issubclass(ValidationError, ValueError) is True`).
- **WR-04 (deny-rule shape unpinned) — CLOSED.** The fixture now carries `PermissionRule`,
  the default-lane snapshot test pins it and routes through a helper with a guard-can-fail
  companion, and the live lane projects the same three facts. A server rename now produces a
  named failing pointer (default lane) or a diff (live lane).
- **IN-05 (raising backend wrote no row, returned 200) — CLOSED.** The route records one
  `error` `purpose='probe'` row, commits it, and returns 500 with the cause
  (`settings.py:427-453`); the new test asserts 500, exactly one row, and the rendered cause.
- **IN-03-from-prior (clean re-ingest clobber) — CLOSED.** The new pipeline test drives the
  update path and asserts the recorded finding survives; it passes.

Regression check: full default suite is **834 passed, 3 deselected** (was 826 passed / 3
deselected before the eight new tests), `ruff check` is clean on all 11 files.

Two Warning-level defects remain, both in the adapter's outer exception handlers and both
carried over unaddressed from the prior review (prior IN-04, and the error-kind taxonomy
leak) — the gap-closure strengthened per-attempt attribution but did not touch the handlers
that run *outside* the retry loop. Neither is a Critical: there is no injection, credential
leak, auth bypass, unbounded call ceiling, or raise-leak from the port, and the newly
persisted surfaces are HTML-autoescaped.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: failures outside the retry loop discard resolved D-12 identity and report `attempts=0`

**File:** `app/llm/opencode_server.py:411-415` (session create), `:508-535` (outer handlers)

**Issue:** `_resolve_model` runs first and succeeds, so `provider_id`/`model_id` are known.
`_create_session` is then called *outside* the per-attempt retry loop, and any transport or
timeout failure there escapes the loop and is caught by one of the outer handlers at
`:508-527`, all of which hard-code `attempts=0` and pass no `provider`/`model`/`agent`.
The same applies to the generic handler at `:528-535` (e.g. a non-JSON 200 from
`_create_session`'s `response.json()`, or `to_message_body`'s wildcard `ValueError`).
Reproduced in-process against a stubbed transport:

```
transport-on-session -> error unreachable attempts= 0 provider= None model= None agent= None
transport-on-message -> error unreachable attempts= 3 provider= p    model= m    agent= None
```

The message-send path is correctly attributed by the loop; the session-create path is not.
Consequences: the `llm_calls` audit row understates the attempt count and nulls the
`provider`/`model` columns whose existence is the stated reason migration 0003 was written
(D-12), even though the values were resolved moments earlier. This is exactly the
attribution property 03-08/03-09 set out to guarantee for per-attempt failures, left
unguaranteed for the session handshake. No test exercises a session-create transport failure
(`test_a_transport_failure_is_a_value` only asserts `error_kind == "unreachable"`), so the
gap is invisible to the suite. Carried over from the prior review's IN-04, unclosed.

**Fix:** Thread the already-resolved identity and the issued count into the outer handlers,
e.g. capture `provider_id`/`model_id` before the `async with` and pass
`attempts=issued, provider=provider_id, model=model_id, agent=agent` in each outer
`_failure(...)`; add a test that fails `_create_session` with `httpx.ConnectError` and
asserts `attempts == 1` and the resolved identity survive.

### WR-02: the generic handler emits a raw exception class name as `error_kind`, outside the D-52 taxonomy

**File:** `app/llm/opencode_server.py:528-535` (specifically `error_kind=type(exc).__name__` at `:531`)

**Issue:** `_failure`'s whole point is that `status` stays one of the four legal
`llm_calls.status` values while `error_kind` carries the *specific cause* from the documented
namespace (`unreachable`, `timeout`, `invalid`, `model_not_found`, `invalid_session`,
`http_<code>`). The generic handler instead writes `type(exc).__name__` directly, so the
recorded `error_kind` can be an implementation class name — demonstrated by passing the
builder's forbidden wildcard:

```
tools=('*',) -> error ValueError attempts= 0 err= ValueError: the deprecated 'tools' map ...
```

Any operator/UI logic that switches on the D-52 taxonomy cannot classify `ValueError`,
`JSONDecodeError`, or `TypeError`. `attempts` is also dropped to 0 here (same root as
WR-01). The behaviour is fail-closed (the failure is still a value), but it degrades the
observability contract this phase is built around.

**Fix:** map unexpected exceptions to a stable label (e.g. `error_kind="internal_error"`,
with the class name kept only in `error` for the operator), and preserve `attempts`/identity
as in WR-01.

## Info

### IN-01: `tools: Sequence[str]` accepts a bare `str` and expands it per character

**File:** `app/llm/opencode_server.py:420`; port signature `app/llm/base.py:121`

**Issue:** A single `str` satisfies `Sequence[str]` both statically and at runtime, so
`tools="read"` does not mean "grant read" — the comprehension iterates characters:

```text
converted grant for tools='read': {'r': True, 'e': True, 'a': True, 'd': True}
emitted tools: {'r': True, 'e': True, 'a': True, 'd': True}
```

No exception, no diagnostic; the session `permission` deny still backstops, so it fails safe,
but a Phase 5 caller using a single-name string gets a silent nonsense grant. (The same
`Sequence[str]`-vs-`str` footgun exists for `parts`, which is pre-existing.)

**Fix:** reject a bare `str` explicitly (`if isinstance(tools, str): raise TypeError(...)`),
or tighten the port type and document that callers pass a tuple/list.

### IN-02: the `except ValueError` message over-claims that the payload was "not valid JSON"

**File:** `app/llm/opencode_server.py:820-842`

**Issue:** The clause catches *any* `ValueError` escaping `_salvage`, but only
`from_json(..., allow_partial=True)` is currently a raw-`ValueError` source; the message
"structured payload was not valid JSON" is correct today. `_salvage` is generic over the
caller's schema, so a future schema whose validator surfaces a raw `ValueError` (rather than
a pydantic-wrapped `ValidationError`) would be misdiagnosed and mislabelled `invalid` with a
factually wrong cause. Low likelihood, but the failure mode is a misleading operator message.

**Fix:** narrow the catch to the parse step — e.g. wrap the `from_json` call in `_salvage`
in its own `try/except ValueError` that raises a dedicated exception type, and classify that
type here — or reword the message to "structured payload could not be parsed/validated".

### IN-03: the reusable pointer helper still is not used by the request/response assertions

**File:** `tests/llm/test_contract_snapshot.py:62-80` vs `:139-145`, `:193-209`

**Issue:** Prior review IN-01. `_missing_pointers` still carries the docstring "so the
guard-can-fail companion exercises the SAME code path the real assertion uses", but
`test_the_request_side_contract_matches_the_snapshot` and
`test_the_response_side_contract_matches_the_snapshot` keep inline membership assertions,
so only `test_the_pointer_check_can_actually_fail` runs the helper. The new permission check
does route the real assertion through `_missing_permission_pointers`, making the asymmetry
more visible rather than less.

**Fix:** express the real assertions as `_missing_pointers(...) == []` (as the permission
test now does), or drop the helper and rewrite the companion against the inline assertion.

### IN-04: untrusted body/exception text is persisted into `llm_calls.error` without redaction or a length cap

**File:** `app/llm/opencode_server.py:575-583` / `:678-691` (prior IN-06, unchanged) and
`app/api/settings.py:430` (new surface added by 03-09)

**Issue:** The non-200 response-body excerpt (up to 200 chars) is written to `result.error`,
persisted to the `Text` column `llm_calls.error`, and rendered (`settings.html:55`). The
03-09 raise path adds a second, unbounded feed: `error=f"{type(exc).__name__}: {exc}"` is
persisted and rendered too. Today every writer is a canned selftest body or a library
exception, so the exposure is theoretical; once Phase 5 routes CV/listing content through
this port, a server/proxy error page (or a future adapter exception embedding the request)
could persist a fragment of personal data into an audit column that
`tests/db/test_no_pii_columns.py` does not treat as PII (it is plain `Text`, not a JSON
column). Enlarged in scope by the change under review; still Info because no current caller
sends sensitive content.

**Fix:** before the LLM path carries real content, cap and redact the persisted `error`
(e.g. status line + exception class only, fixed `NON_200_BODY_EXCERPT_CHARS` ceiling on both
surfaces), and document the decision where `NON_200_BODY_EXCERPT_CHARS` lives.

---

## Verified clean (selected focus areas)

- **Tool grant forwarding (WR-01 closure):** `tool_grant` is built once and forwarded to
  `to_message_body`; empty stays `None` so no `tools` key is emitted; the builder's wildcard
  guard still fires. End-to-end tests use `complete_structured`, not the builder directly.
- **Retry ceiling (WR-02 closure):** `retries: int | None = None` on both Protocol and
  adapter; `budget = retries if retries is not None else settings.opencode_max_retries`;
  explicit bounds honoured; `max(1, ...)` keeps `retries=0` at one attempt. Setting-patched
  test observes 7 attempts.
- **Parse-failure classification (WR-03 closure):** `except ValidationError` precedes
  `except ValueError` (subclass relation verified); the new branch preserves
  `provider`/`model`/`agent`/`part_types`/`info_keys` and `attempts`; `raw` stays `None` on
  every failure branch.
- **Deny-rule contract (WR-04 closure):** fixture `PermissionRule` slice; default-lane test
  pins properties/required/action and has a guard-can-fail companion; live lane projects the
  same facts for a real diff. `additionalProperties: false` invariants asserted where the
  builder/receivers rely on them.
- **Raising-backend path (IN-05 closure):** exactly one committed `probe` row, `run_id`
  NULL, `status='error'`, exception class in `error`, HTTP 500; page names the cause. No
  `runs` row created (D-50 intact).
- **Clean re-ingest (T-3-21):** `upsert_listing`'s update branch applies
  `if value is not None`, and `NormalisedListing.quality_signals_json` returns `None` (not
  `{}`) for a clean payload; the new two-run test exercises and passes the update path.
- **Trust boundary:** `SELFTEST_SYSTEM_PROMPT` remains an AST-verified single `Constant`;
  `parts` is the only untrusted channel; the wildcard is rejected in the deprecated `tools`
  map; the observation carries part/key names only (sentinel tests cover log + DB + page).
- **Privacy/redaction:** discovery identifiers only; `ProviderModel`/`StructuredCallResult`
  `extra="forbid"`; `raw` never persisted or logged; no new secret in the fixture or tests.
- **Prompt-injection handling:** the counts-only finding is stored on
  `listings.quality_signals_json`; no matched text/excerpt/position reaches the DB or page.
- **Default suite:** 834 passed / 3 deselected; `ruff check` clean on the changed files.

---

_Reviewed: 2026-09-18T10:54:12Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
