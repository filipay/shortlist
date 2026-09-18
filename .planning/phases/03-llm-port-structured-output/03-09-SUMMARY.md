---
phase: 03-llm-port-structured-output
plan: 09
subsystem: llm
tags: [opencode, contract-test, permission-deny, audit-trail, pydantic, pytest]

# Dependency graph
requires:
  - phase: 03-llm-port-structured-output
    provides: 03-01 the /settings selftest route and llm_calls probe write path
  - phase: 03-llm-port-structured-output
    provides: 03-02 the committed /doc slice and the default-lane snapshot contract
  - phase: 03-llm-port-structured-output
    provides: 03-06 the session-level DEFAULT_DENY_RULES tool deny
  - phase: 03-llm-port-structured-output
    provides: 03-07 the counts-only instruction-like finding and T-3-21 nullable guard
provides:
  - "The PermissionRule deny-rule shape pinned in the committed /doc slice, the default-lane snapshot test, and the operator live projection"
  - "A raising LLM backend recorded as an error llm_calls probe row and reported with a 500, with the cause rendered"
  - "An update-path proof that a clean re-ingest preserves a recorded instruction-like signal"
affects: [05-ranking, 06-tailoring, opencode-contract-refresh-runbook, listing-reingest]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
# Same estimateTokens scale (chars/4 over the realized diff), never a harness token count.
actuals:
  tokens: 4373
  tasks: 3
  commits: 3
  plan_head_before: 6fbf3302258a33d49ead3050e6dcad181b799d90

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Contract-pin with a guard-can-fail companion: the real assertion and its negative control call the SAME reusable pointer helper, so a guard that cannot fail is caught"
    - "Audit-before-response: a backend that violates the port's total-function contract still leaves one llm_calls row before the HTTP status is chosen"
    - "Update-path guard proof: exercise upsert_listing's update branch explicitly by re-running against the same source_listing_id"

key-files:
  created: []
  modified:
    - tests/llm/fixtures/opencode-doc.json
    - tests/llm/test_contract_snapshot.py
    - tests/llm/test_contract_live.py
    - app/api/settings.py
    - tests/api/test_llm_selftest.py
    - tests/pipeline/test_injection_finding.py

key-decisions:
  - "D-55 widened deliberately: the committed /doc slice now also pins the session deny-rule field names and the deny action, because the permission ruleset is the ENFORCED tool control; _meta.note records the widening"
  - "The live projection follows the session permission array's items.$ref (with a one-level wrapper follow and a PermissionRule-name fallback) so a renamed/reshaped rule reports drift instead of resolving to an empty schema"
  - "The raise branch records the attempt BEFORE replying and returns 500 (the reset route's convention for an unexpected internal failure), rather than lying with a 200"

patterns-established:
  - "A contract pin ships with a reusable failing-pointer helper and a negative-control test asserting decoy names produce a non-empty list"
  - "Every route branch that can spend tokens persists its audit row before choosing the response status"

requirements-completed: [PLAT-05, PLAT-02]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "A server-side rename of the permission/pattern/action rule fields or a drop of the deny action fails the default-lane contract test with no server running"
    requirement: PLAT-05
    verification:
      - kind: unit
        ref: "tests/llm/test_contract_snapshot.py#test_the_permission_deny_rule_contract_matches_the_snapshot"
        status: pass
      - kind: unit
        ref: "tests/llm/test_contract_snapshot.py#test_the_permission_pointer_check_can_actually_fail"
        status: pass
    human_judgment: false
  - id: D2
    description: "The operator live lane diffs the deny-rule properties, required fields and action enum against the committed slice"
    requirement: PLAT-05
    verification:
      - kind: unit
        ref: "tests/llm/test_contract_live.py --collect-only -m live (collection only; the diff needs a running server)"
        status: pass
    human_judgment: true
    rationale: "The live /doc diff is operator-run against a real opencode server (D-57); the default lane structurally cannot reach it, so a human must run the live lane on the host."
  - id: D3
    description: "A raising backend writes exactly one error llm_calls probe row and returns HTTP 500 naming the cause, with no runs row"
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/api/test_llm_selftest.py#test_a_raising_backend_returns_500_and_writes_one_audit_row"
        status: pass
    human_judgment: false
  - id: D4
    description: "A clean re-ingest of an already-flagged listing preserves the recorded instruction-like signal on the update path"
    requirement: PLAT-02
    verification:
      - kind: unit
        ref: "tests/pipeline/test_injection_finding.py#test_a_clean_reingest_preserves_the_recorded_signal"
        status: pass
    human_judgment: false

# Metrics
duration: 13min
completed: 2026-09-18
status: complete
---

# Phase 3 Plan 09: Close the deny-rule, audit-raise and re-ingest warnings Summary

**Pinned the session permission deny-rule shape against `/doc` drift, made a raising LLM backend auditable with an honest 500, and proved the T-3-21 nullable guard survives a clean re-ingest.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-09-18T10:25:21Z
- **Completed:** 2026-09-18T10:38:01Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Wired the enforced `DEFAULT_DENY_RULES` tool deny into the `/doc` contract pin: the committed slice now carries a `PermissionRule` entry (`permission`/`pattern`/`action`, action enum `allow|ask|deny`), a default-lane snapshot test asserts it, a guard-can-fail companion proves the check has teeth, and the operator live projection emits the same three fact keys so `_diff_facts` names the rule pointers on drift.
- Made the `/settings/llm-test` raise branch auditable and honest: a backend that raises now writes exactly one `error` `llm_calls` probe row (`run_id IS NULL`, no `runs` row) before the response, and returns HTTP 500 with the cause in the banner — matching the reset route's 400/409/500 convention.
- Proved the nullable-guard design on the update path: a clean re-ingest against the same `source_listing_id` leaves one listing whose `quality_signals_json` still has `instruction_like is True` and the original integer `patterns_matched`, with no instruction prose stored.

## Task Commits

Each task was committed atomically:

1. **Task 1: Pin the session permission-rule shape so a rename cannot silently un-deny** - `ea615e9` (test)
2. **Task 2: A raising backend is auditable and returns an honest status** - `9880ad3` (fix)
3. **Task 3: A clean re-ingest preserves a recorded instruction-like signal** - `b219fd1` (test)

_No TDD plan (phase.tdd-applicable = false); no RED/GREEN commits._

## Files Created/Modified

- `tests/llm/fixtures/opencode-doc.json` — added `components.schemas.PermissionRule` (`properties`, `required`, `action_enum`) and recorded the deliberate D-55 widening in `_meta.note`
- `tests/llm/test_contract_snapshot.py` — `test_the_permission_deny_rule_contract_matches_the_snapshot`, the reusable `_missing_permission_pointers` helper, and `test_the_permission_pointer_check_can_actually_fail`
- `tests/llm/test_contract_live.py` — `_permission_rule_schema` walk plus `permission_rule_properties`/`permission_rule_required`/`permission_action_enum` in both `_live_facts` and `_committed_facts`
- `app/api/settings.py` — the audited `except Exception` branch (record + commit + `status_code=500`) and the corrected route docstring
- `tests/api/test_llm_selftest.py` — `test_a_raising_backend_returns_500_and_writes_one_audit_row`
- `tests/pipeline/test_injection_finding.py` — `test_a_clean_reingest_preserves_the_recorded_signal`

## Decisions Made

- **D-55 widening recorded, not hidden.** Extending the committed `/doc` slice with the `PermissionRule` shape is a deliberate, user-approved widening because the deny ruleset is the enforced tool control; `_meta.note` records it and still contains `"static spec version"`, so `test_the_meta_records_the_observed_server_and_the_spec_source` stays green.
- **Live-side resolution is drift-sensitive, not adaptive.** The projection follows the session `permission` array's `items.$ref` into `components.schemas` (with a one-level wrapper follow), falling back to the literal `PermissionRule` name — so a renamed rule yields an empty committed-vs-live mismatch rather than silently agreeing.
- **Raise branch mirrors the value path.** The recorded row is passed to `_settings_context(probe=record, probe_error_kind=failure.error_kind)`, so the immediate render and a later `latest_probe` reload show the same audited detail.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The full suite grew from the plan's 826-passed baseline to **834 passed, 3 deselected** (the +4 from plan 03-08 plus the +4 new tests here), with no failures.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- WR-04 closes: the deny-rule shape is pinned in the fixture, the default-lane test and the live projection, so a server-side rename can no longer silently turn the enforced deny into a no-op.
- The `200-on-raise` warning closes: the attempt is audited and the status is 500.
- The missing clean-re-ingest test is added and green.
- Still operator-run and human: the live `/doc` drift lane needs a running `opencode serve`; the live schema-constrained call and trust-boundary observation remain the phase's end-of-phase human checks (03-VERIFICATION.md).

---

*Phase: 03-llm-port-structured-output*
*Completed: 2026-09-18*

## Self-Check: PASSED
