---
phase: 06-tailoring-verification
plan: 09
subsystem: api
tags: [tailoring, audit-trail, llm-calls, error-handling, wr-01, tail-02]

requires:
  - phase: 06-tailoring-verification
    provides: "the tailoring generate path (tailor_listing + generate route) and the shared in-flight budget lock"
provides:
  - "a raised complete_structured writes exactly one purpose=tailor status=error llm_calls row (WR-01 closed)"
  - "the generate route reaches its typed 502 data-error=tailoring_failed refusal instead of a bare 500"
  - "the exception CLASS name only crosses into llm_calls.error and the log (no message)"
  - "the shared in-flight budget slot is released on the exception path"
affects: [phase-07-application-tracker, tailoring-cost-audit]

actuals:
  tokens: 2489
  tasks: 2
  commits: 2
  plan_head_before: 318329bc03928458ea7e9d1068ef7dfedea6ec49

tech-stack:
  added: []
  patterns:
    - "value-returning error contract: an attempted LLM call records exactly one audit row and returns None on any failure, never re-raising to the route"
    - "class-only redaction on the error path: type(exc).__name__ is recorded and logged, never str(exc)"

key-files:
  created: []
  modified:
    - app/pipeline/tailor.py
    - app/api/tailoring.py
    - tests/pipeline/test_tailor_stage.py
    - tests/api/test_tailoring_generate.py

key-decisions:
  - "The raised-call error row records the exception CLASS name only, deliberately diverging from the review's f\"{type(exc).__name__}: {exc}\" snippet — a transport message can echo request context and T-06-07 forbids a redaction-hostile field"
  - "The route's typed refusal is its EXISTING patch-is-None branch; no second try/except is added around tailor_listing, since it would be dead code once the pipeline stops raising"
  - "Every ATTEMPTED call writes exactly one llm_calls row, including a raise — the audit trail is the promise, not a side effect of success"

patterns-established:
  - "A raise in a value-returning pipeline function is caught, audited and turned into a value so the caller's typed branch is the only response surface (no bare 500)"
  - "The finally clause owns the shared budget release on both the success and exception paths"

requirements-completed: [TAIL-02]

coverage:
  - id: D1
    description: "A raised complete_structured writes exactly one purpose=tailor, status=error llm_calls row and the generate route returns 502 data-error=tailoring_failed (never a 500)"
    requirement: "TAIL-02"
    verification:
      - kind: integration
        ref: "tests/api/test_tailoring_generate.py#test_generate_returns_a_typed_error_and_one_audit_row_when_the_backend_raises"
        status: pass
    human_judgment: false
  - id: D2
    description: "The pipeline returns None on a raised call, records a class-only error row, and releases the shared in-flight budget slot"
    requirement: "TAIL-02"
    verification:
      - kind: unit
        ref: "tests/pipeline/test_tailor_stage.py#test_a_raised_backend_error_still_writes_one_tailor_row_and_returns_none"
        status: pass
    human_judgment: false
  - id: D3
    description: "The success path and the value-returning (ok=False) failure path are unchanged: one call, one patch, one row, None on model failure"
    requirement: "TAIL-02"
    verification:
      - kind: integration
        ref: "tests/api/test_tailoring_generate.py#test_generate_returns_the_review_fragment_and_writes_nothing"
        status: pass
      - kind: unit
        ref: "tests/pipeline/test_tailor_stage.py#test_a_failed_call_writes_one_tailor_row_and_returns_none"
        status: pass
      - kind: unit
        ref: "tests/pipeline/test_tailor_stage.py#test_a_successful_call_writes_one_tailor_row_with_a_null_run_id"
        status: pass
    human_judgment: false

duration: 11 min
completed: 2026-09-25
status: complete
---

# Phase [6] Plan [09]: WR-01 — a raised tailoring transport error writes its audit row and becomes a typed refusal, not a 500

**The tailoring generate path now records exactly one class-only `llm_calls` row for an attempted call even when `complete_structured` raises, releases the shared in-flight budget slot, and surfaces the route's typed 502 `tailoring_failed` refusal instead of a bare 500.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-09-25T09:10:00Z
- **Completed:** 2026-09-25T09:21:28Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `tailor_listing` gained an `except Exception as exc` (with `# noqa: BLE001`) that writes one `purpose="tailor"`, `status="error"`, `run_id=None` `llm_calls` row with `error=type(exc).__name__`, logs `pipeline.tailor_transport_error` with the class only, and returns `None` — the attempted (and possibly billed) call is never invisible (T-06-39).
- The `finally: _release()` is retained, so the shared in-flight budget slot is released on the exception path exactly as on success (T-06-42); a transport failure cannot wedge later tailoring calls.
- The generate route reaches its existing `patch is None` branch, which IS the typed refusal: HTTP 502 with `data-error="tailoring_failed"` — no request becomes a bare 500 (T-06-41). Its docstring now records the contract so the asymmetry cannot be "fixed" back into an escape.
- Only the exception CLASS name crosses into the ledger and the log; `str(exc)` is never used, preserving T-06-07's redaction posture (T-06-40).
- Both the success path (one call, one `ok` row, one patch) and the value-returning `ok=False` failure path are unchanged.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end — a raising backend yields one audit row and a typed 502, never a 500** - `2d6bbe5` (fix)
2. **Task 2: Pin the value-returning contract and the released budget slot at the pipeline level** - `343bb56` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `app/pipeline/tailor.py` - `tailor_listing` gains the `except` audit/return clause and an updated docstring stating the per-attempt audit and value-returning contracts.
- `app/api/tailoring.py` - `generate_tailored_cv`'s docstring records that a `None` return is the typed 502 `tailoring_failed` refusal and no transport failure escapes.
- `tests/pipeline/test_tailor_stage.py` - `StubBackend` gains `raise_on_call`; new `test_a_raised_backend_error_still_writes_one_tailor_row_and_returns_none`.
- `tests/api/test_tailoring_generate.py` - `TailoringStubBackend` gains `raise_transport` (reset in `_reset_stubs`); new `_llm_call_rows` helper and `test_generate_returns_a_typed_error_and_one_audit_row_when_the_backend_raises`.

## Decisions Made
- **Class-only redaction.** The review's suggested snippet recorded `f"{type(exc).__name__}: {exc}"`; this plan records the class name only, a deliberate privacy-forward divergence — a transport message can echo request context and T-06-07 forbids a redaction-hostile field. The route test's `error == "RuntimeError"` assertion enforces it.
- **No redundant route try/except.** The route's typed refusal is its existing `patch is None` branch; a second guard would be dead code once the pipeline stops raising.
- **Audit the attempt, not the success.** Exactly one row per attempted call is the contract; the except writes it before returning `None`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Threat Flags

None — no new security-relevant surface. The changes implement the plan's mitigations: T-06-39 (attempt audited), T-06-40 (class-only redaction), T-06-41 (typed 502, not 500), T-06-42 (slot released). No table, column, Settings field or migration was touched; the Alembic head stays `0004`.

## Next Phase Readiness
- WR-01 is closed: a backend transport failure is an audited value on the generate path, and the request gets a typed 502 fragment.
- `metric_containment`/verifier behaviour is untouched by this plan.
- Full hermetic lane green: 1238 passed, 14 deselected, 2 xfailed (1236 prior + 2 new tests). Scheme 06-08 and 06-09 are both complete; no outstanding plans remain for Phase 06.

## State/ROADMAP

Deliberately NOT updated by this executor — the orchestrator owns those shared-file writes for this plan.

---
*Phase: 06-tailoring-verification*
*Completed: 2026-09-25*

## Self-Check: PASSED

- All 4 created/modified files exist on disk.
- Both task commits present: `2d6bbe5`, `343bb56`.
- `.venv/bin/python -m pytest -q tests/api/test_tailoring_generate.py -x` — 6 passed.
- `.venv/bin/python -m pytest -q tests/pipeline/test_tailor_stage.py -x` — 10 passed.
- `.venv/bin/python -m pytest -q tests/api/test_tailoring_generate.py tests/pipeline/test_tailor_stage.py tests/api/test_tailoring_review.py -x` — 34 passed.
- Full lane `.venv/bin/python -m pytest -q` — 1238 passed, 14 deselected, 2 xfailed; `compileall -q app` clean.
- STATE.md and ROADMAP.md left untouched.
