---
phase: 03-llm-port-structured-output
plan: 03
subsystem: llm-port
tags: [opencode, structured-output, failure-taxonomy, retry, salvage, pydantic, tdd]

# Dependency graph
requires:
  - phase: 03-llm-port-structured-output
    provides: "plan 03-01's complete_structured happy path, StructuredCallResult, and the Recorder fake transport"
provides:
  - "The full D-52 failure taxonomy inside app/llm/opencode_server.py: every observed condition maps onto one of the four legal llm_calls.status values with an operator-facing error_kind"
  - "A bounded client-side retry loop governed by the retries argument, distinct from the server-side format.retryCount ceiling"
  - "TOLERATED_SCHEMA_ERRORS + _salvage: partial JSON salvaged through an explicit allow-list, wired into complete_structured"
affects: [03-04, 03-05, 03-06, 03-07, 05-ranking]

# Actuals (#2632) — same estimateTokens scale (chars/4) as the plan's estimate.
actuals:
  tokens: 9271
  tasks: 2
  commits: 4

# Tech tracking
tech-stack:
  added: []   # zero new packages; tenacity deliberately left unused
  patterns:
    - "Failure as a classified value: status stays inside the four legal values, the cause lives in error_kind (D-52)"
    - "Two retry layers, deliberately different: server-side format.retryCount vs a client loop bounded by the retries argument"
    - "Salvage only through an explicit frozenset allow-list; 'any error' is forbidden (M1)"
    - "PydanticUseDefault never used in production: a tolerated error substitutes the default by removing the field, so a default-less field re-raises instead of leaking the marker (P11)"

key-files:
  created:
    - tests/llm/test_salvage.py
  modified:
    - app/llm/opencode_server.py
    - tests/llm/test_complete_structured.py

key-decisions:
  - "status is always one of ok/invalid/timeout/error; the operator cause (unreachable, timeout, invalid, http_<code>, parse-exception type) is carried in error_kind, so the ck_llm_calls_status vocabulary is never extended."
  - "ConnectTimeout is classified error/unreachable (connection never established) while ReadTimeout is timeout — the plan's explicit behaviour, refining the research table's blanket TimeoutException -> timeout."
  - "The retry budget is derived from the caller's `retries` argument (Settings supplies only the default); a schema failure is never retried client-side because the server already ran format.retryCount, and double-retrying would inflate the operator's attempt count."

patterns-established:
  - "A failure branch always leaves raw=None, so no response body can be persisted by accident (P9/T-3-05)"
  - "attempts is the server's info.error.data.retries when supplied, and the client's issued-request count otherwise — never a literal"

requirements-completed: [PLAT-02]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "Every structured-call failure is classified: StructuredOutputError -> invalid (attempts from info.error.data.retries), ValidationError -> invalid, ConnectError/ConnectTimeout -> error/unreachable, ReadTimeout -> timeout, non-200 -> error/http_<code> with a bounded excerpt, unparseable JSON -> error naming the parse exception."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_a_structured_output_error_is_invalid_with_the_servers_attempt_count"
        status: pass
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_a_connect_error_is_unreachable"
        status: pass
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_a_read_timeout_is_a_timeout"
        status: pass
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_a_non_200_yields_http_kind_and_a_bounded_excerpt"
        status: pass
    human_judgment: false
  - id: D2
    description: "The client retry loop is bounded by the caller's retries argument, a schema failure is never retried client-side, and the emitted format.retryCount is the separate Settings structured ceiling."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_the_client_loop_is_bounded_by_the_retries_argument"
        status: pass
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_a_schema_failure_is_not_retried_client_side"
        status: pass
      - kind: unit
        ref: "tests/llm/test_complete_structured.py#test_the_sent_body_carries_the_configured_server_retry_count"
        status: pass
    human_judgment: false
  - id: D3
    description: "A truncated structured payload salvages to a validated object; a tolerated missing field falls back to defaults; an untolerated mismatch still fails loudly; the allow-list is exact and load-bearing; the P11 no-default marker leak is pinned."
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/llm/test_salvage.py#test_a_truncated_json_string_salvages_with_the_readable_fields_intact"
        status: pass
      - kind: unit
        ref: "tests/llm/test_salvage.py#test_an_untolerated_schema_mismatch_is_not_salvaged"
        status: pass
      - kind: unit
        ref: "tests/llm/test_salvage.py#test_pydantic_use_default_leaks_on_a_field_with_no_default"
        status: pass
      - kind: unit
        ref: "tests/llm/test_salvage.py#test_the_allow_list_is_load_bearing"
        status: pass
    human_judgment: false
  - id: D4
    description: "complete_structured actually uses the salvage path: a usable-but-truncated info.structured string returns ok=True with the readable fields intact."
    requirement: PLAT-02
    verification:
      - kind: integration
        ref: "tests/llm/test_salvage.py#test_complete_structured_salvages_a_truncated_structured_string"
        status: pass
    human_judgment: false

# Metrics
duration: 9 min
completed: 2026-09-17
status: complete
---

# Phase 3 Plan 03: LLM Port + Structured Output Summary

**Every way a structured call can fail now produces a classified, counted outcome — `ok`/`invalid`/`timeout`/`error` plus an operator-facing cause and an honest attempt count — and a truncated payload salvages through an explicit allow-list while a genuine mismatch still fails loudly.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-09-17T21:23:30Z
- **Completed:** 2026-09-17T21:32Z
- **Tasks:** 2 (both TDD)
- **Files created/modified:** 3 (1 created, 2 modified)
- **Full suite:** 777 passed, 3 deselected (~105 s; plan 03-02 baseline was 757 passed, 3 deselected)

## Accomplishments

- **Failure is now a classified value, never a silent success.** `complete_structured` maps every observed condition onto the four legal `llm_calls.status` values, with D-52's operator cause in `error_kind`: `unreachable`, `timeout`, `invalid`, `http_<code>`, or the parse exception's type.
- **The attempt count is honest and sourced.** A `StructuredOutputError` yields `attempts` from the server's own `info.error.data.retries`; a transport failure yields the client's issued-request count. A test asserts `attempts` against the fake's recorded request count, so a literal cannot pass.
- **The two retry layers are separate and both configured.** The client loop is bounded by the caller's `retries` argument (`Settings.opencode_max_retries` supplies the default); `format.retryCount` carries `settings.opencode_structured_retry_count`. A schema failure is never retried client-side.
- **Salvage is allow-list-only.** `TOLERATED_SCHEMA_ERRORS = frozenset({"missing", "int_parsing"})`; a truncated JSON tail is dropped by `from_json(..., allow_partial=True)`, and a tolerated error substitutes a default. An untolerated mismatch still fails as `invalid`.
- **Nothing leaks.** Every failure branch leaves `raw=None`; the non-200 body excerpt is bounded by `NON_200_BODY_EXCERPT_CHARS = 200`; the test asserts no sentinel reaches `vars(result)`.
- **No new dependency.** `tenacity` is deliberately unused (the research warns `AsyncRetrying` collapses the per-attempt classification D-52 needs), asserted by a source check.

## Task Commits

Each task was committed atomically with the TDD RED → GREEN sequence:

1. **Task 1: The failure taxonomy and the bounded retry** — `0f3f734` (test, RED) → `8da7943` (feat, GREEN)
2. **Task 2: The salvage path** — `f5bcfaa` (test, RED) → `1b84a25` (feat, GREEN)

**Plan metadata:** the `docs(03-03)` commit immediately following this file (SUMMARY + STATE + ROADMAP + REQUIREMENTS).

## Files Created/Modified

- `app/llm/opencode_server.py` — **modified**; `ERROR_KIND_*` labels and the `http_` prefix, `NON_200_BODY_EXCERPT_CHARS`, `TOLERATED_SCHEMA_ERRORS`, `_tolerant_validator`, `_salvage`, `_failure`, `_bounded_excerpt`, `_classify_message_response`, and the rewritten total `complete_structured` with the bounded retry loop
- `tests/llm/test_complete_structured.py` — **modified**; the classification/retry matrix and a per-endpoint `Recorder` (session vs message status/error/text)
- `tests/llm/test_salvage.py` — **created**; the allow-list, truncation, P11 and wiring tests

## Decisions Made

- **`status` never grows.** The specific cause is `error_kind`, keeping `ck_llm_calls_status`'s four values intact.
- **`ConnectTimeout` is `unreachable`, `ReadTimeout` is `timeout`.** The plan's explicit behavior; the research table's blanket "TimeoutException → timeout" is refined because failing to establish a connection is operationally different from a slow response.
- **The salvage substitutes defaults by removing the field, not by returning `PydanticUseDefault()`.** The wrapper is still a `WrapValidator`, but this form cannot leak the marker object on a default-less field — it re-raises `missing` instead, which is exactly the P11 safety property the plan asks to pin.
- **`attempts` on a schema failure is the server's count, not the client loop's.** The server already ran the schema retries; double-counting would mislead the operator.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The salvage mechanism avoids the P11 marker leak rather than reproducing it**
- **Found during:** Task 2 (salvage implementation)
- **Issue:** The plan's `<action>` suggested re-validating "through a `WrapValidator` that returns `PydanticUseDefault()`". That literal form leaks the marker object onto any tolerated field that has no default — the exact pitfall P11 warns about.
- **Fix:** kept the `WrapValidator` shape but had it remove the offending top-level field from a copy and re-validate, so a defaulted field takes its default and a default-less field re-raises `missing`. Every behavior test passes, and `test_salvage_refuses_a_tolerated_field_with_no_default` pins the safer outcome.
- **Files modified:** `app/llm/opencode_server.py`, `tests/llm/test_salvage.py`
- **Verification:** `tests/llm/test_salvage.py` 9 passed; full suite green.
- **Committed in:** `1b84a25` (Task 2 GREEN)

**2. [Rule 1 - Bug] The fake transport had to expose the exception types the module catches**
- **Found during:** Task 1 GREEN (first run of the new matrix)
- **Issue:** the `Recorder` monkeypatches the module's `httpx` name, so `except httpx.TimeoutException` resolved against the fake namespace and raised `AttributeError`; and `json_error` applied to the session response as well as the message response, so the unparseable-JSON test never reached the classifier.
- **Fix:** the fake now exposes `TimeoutException`/`TransportError`/`ConnectTimeout`, and the message-only `json_error` is attached per response.
- **Files modified:** `tests/llm/test_complete_structured.py`
- **Verification:** `tests/llm/test_complete_structured.py` 25 passed.
- **Committed in:** `8da7943` (Task 1 GREEN)

---

**Total deviations:** 2 auto-fixed (2 bugs, both internal to the new code/tests)
**Impact on plan:** Neither changed the plan's contract; the first made the P11 guarantee stronger, the second was required for the new tests to exercise the taxonomy at all. No scope creep, no new dependency.

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR | Notes |
|------|-----|-------|----------|-------|
| 1 | `0f3f734` (test) | `8da7943` (feat) | — | RED was a **genuine assertion failure**: 10 target tests failed against the happy-path-only implementation (wrong `error_kind`, no retry bound, `attempts=0`, `retryCount` = the client ceiling). |
| 2 | `f5bcfaa` (test) | `1b84a25` (feat) | — | RED was a **genuine assertion failure**: 7 target tests failed because `_salvage`/`TOLERATED_SCHEMA_ERRORS` did not exist; the P11 local-model demonstration passed independently. |

## Issues Encountered

- **The `attempts` semantics needed a deliberate split.** The server's `data.retries` and the client's issued-request count are different measurements; the taxonomy reports the former when the server supplies it and the latter otherwise, and two tests pin both.
- **The `WrapValidator` on `info.structured` only matters for string payloads.** The live server returns `info.structured` as an object, so the `allow_partial` path is exercised by the direct `_salvage` tests and the dedicated wiring test (a truncated string), not by a live call — which is correct: the salvage is a degradation boundary, not the normal path.

## Known Stubs

None. Every branch in this plan's taxonomy is implemented and tested in the default lane; nothing is deferred to a later plan.

## Threat Flags

None — no new surface. This plan mitigates T-3-01 (allow-list only), T-3-14 (classified, counted failures), T-3-05 (bounded excerpt, `raw=None` on failures), T-3-06 (both ceilings are `Settings` fields, the loop is explicitly bounded) and T-3-SC (`tenacity` not imported, no new package), all already in the plan's threat register.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **The backend now degrades honestly.** Phase 5's ranking caller can rely on `status` + `error_kind` + `attempts` to decide whether to surface, retry at a higher level, or record an `invalid` outcome — a silently empty ranking result is no longer reachable through this path.
- **`record_llm_call` already accepts the mapped fields** (plan 03-01), so the selftest route and Phase 5 both persist this taxonomy unchanged.
- **`PLAT-02` remains open by design.** It is declared by six plans; the shared-ID gate keeps it incomplete until the last declaring sibling (03-04..03-07) has a SUMMARY.md.
- **No operator action is required for this plan.** All of its verification runs in the default lane.

---
*Phase: 03-llm-port-structured-output*
*Completed: 2026-09-17*

## Self-Check: PASSED

- All three plan files exist on disk (`app/llm/opencode_server.py`, `tests/llm/test_complete_structured.py`, `tests/llm/test_salvage.py`).
- All four plan commits are present (`0f3f734`, `8da7943`, `f5bcfaa`, `1b84a25`).
- Measured commit count from the plan ledger: 4 (`git rev-list --count 1b60986..HEAD`).
