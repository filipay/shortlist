---
phase: 07-assisted-apply-tracker
plan: 14
subsystem: domain
tags: [pydantic, coercion, wire-schema, wr-01, g-07-7, fail-closed]

requires:
  - phase: 07-assisted-apply-tracker
    provides: "G-07-7 shared coercion helper (app/domain/schemas/_coerce.py) and the single-key {\"item\": ...} unwrap on every list-typed wire field"
provides:
  - "WRAPPER_KEY = \"item\" module constant; unwrap_single_key_mapping recognises only the literal wrapper key"
  - "bounded unwrap loop (breaks when inner is outer) so a caller-constructed self-reference cannot hang"
  - "TailoringPatch.ops/.gaps/.suggestions before-validators delegating to coerce_mapping_list (IN-01)"
  - "failure-class tests (unknown key with a LIST value; items/value/data) replacing the two scalar false-name tests"
affects: [07-verify]

actuals:
  tokens: 3276
  tasks: 3
  commits: 3
plan_head_before: 16d2d728ccad1eb46d7c0a908522de38e56df230

tech-stack:
  added: []
  patterns:
    - "The coercion boundary is the single place that decides which non-array shapes are laundered into valid arrays; a docstring promise there is load-bearing and must be delivered by the code (CONVENTIONS rule 6)"
    - "Failure-class tests pass a LIST under an unknown key, so the test fails on the unknown key rather than on a scalar (CONVENTIONS rule 4)"

key-files:
  created: []
  modified:
    - app/domain/schemas/_coerce.py
    - app/domain/cv.py
    - tests/domain/test_coerce.py
    - tests/domain/test_screening_schema.py

key-decisions:
  - "Option (i): the unwrap is restricted to the literal provider wrapper key \"item\" — the documented behaviour becomes true and the fail-closed posture is restored, rather than re-describing a wider acceptance"
  - "IN-02 is closed in the same edit: the loop breaks when `inner is value`, so the exported helper terminates on a caller-constructed self-reference"
  - "IN-01 is closed by routing TailoringPatch's three top-level lists through the same helper; `_Forbid`'s extra=\"forbid\" posture is not weakened because a non-item single-key mapping becomes ONE item and is refused"
  - "TOLERATED_SCHEMA_ERRORS stays {\"missing\", \"int_parsing\"} — widening it to tolerate list_type would substitute the field default and silently discard grounded content (M1)"

patterns-established:
  - "Key-restricted unwrap: a Mapping is unwrapped only when its sole key IS the literal wrapper key; every other single-key mapping is returned UNCHANGED (never partially unwrapped)"
  - "Two distinct loud-failure routes for a Mapping left untouched: list_type via coerce_str_list, the item model's extra=\"forbid\" via coerce_mapping_list — both stated in prose rather than repeated"

requirements-completed: [APPLY-01]

coverage:
  - id: D1
    description: "unwrap_single_key_mapping unwraps only the literal wrapper key \"item\" and is bounded against self-reference"
    requirement: "APPLY-01"
    verification:
      - kind: unit
        ref: "tests/domain/test_coerce.py#test_an_unknown_wrapper_key_with_a_list_value_still_fails_loudly"
        status: pass
      - kind: unit
        ref: "tests/domain/test_coerce.py#test_a_non_item_single_key_still_fails_loudly"
        status: pass
      - kind: unit
        ref: "tests/domain/test_coerce.py#test_a_self_referential_single_key_mapping_terminates"
        status: pass
    human_judgment: false
  - id: D2
    description: "The two scalar false-name tests are REPLACED with the finding's literal list-value class; no test name claims an unknown key while asserting on a scalar"
    requirement: "APPLY-01"
    verification:
      - kind: unit
        ref: "tests/domain/test_screening_schema.py#test_an_unrecognised_mapping_evidence_ids_still_fails_loudly"
        status: pass
    human_judgment: false
  - id: D3
    description: "TailoringPatch.ops/.gaps/.suggestions accept the wrapper and a bare single object via coerce_mapping_list, and a non-item single-key mapping is refused"
    requirement: "APPLY-01"
    verification:
      - kind: unit
        ref: "tests/domain/test_coerce.py#test_a_tailoring_patch_list_field_unwraps_the_wrapper_and_wraps_the_bare_object"
        status: pass
      - kind: unit
        ref: "tests/domain/test_coerce.py#test_a_tailoring_patch_non_item_single_key_mapping_is_refused"
        status: pass
    human_judgment: false
  - id: D4
    description: "Module and helper docstrings state the delivered key restriction and the two failure routes (list_type vs extra=\"forbid\") with no unsupported guarantee"
    human_judgment: true
    verification: []
    rationale: "Whether prose matches behaviour is a judgement call the CONVENTIONS rule 6 reviewer/verifier owns, not an assertion; the fix author does not certify it"

duration: ~9min
completed: 2026-10-12
status: complete
---

# Phase 7 Plan 14: WR-01 Summary

**The single-key wrapper unwrap now recognises only the literal provider key `"item"`, is bounded against self-reference, and its three tests pin the failure CLASS — plus the tailoring patch's three top-level lists join the same helper.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-10-12T14:02:09Z
- **Completed:** 2026-10-12T14:11:15Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- `unwrap_single_key_mapping` unwraps only a Mapping whose sole key IS `WRAPPER_KEY` (`"item"`); every other single-key mapping is returned untouched and fails loudly at pydantic — making the module docstring's claim true rather than aspirational (WR-01).
- The loop is bounded: it breaks when the inner value IS the outer Mapping, so the exported helper cannot hang a caller that constructs `d["item"] = d` (IN-02).
- The two tests that claimed an "unknown key" while passing a SCALAR were replaced (not supplemented) with the finding's literal list-value shape `{"nope": ["bul/x/1"]}`, plus parametrised `items`/`value`/`data` cases — the failure class is pinned (CONVENTIONS rule 4).
- `TailoringPatch.ops` / `.gaps` / `.suggestions` now route through the same `coerce_mapping_list` helper, so every list-typed field on the salvage path has one behaviour (IN-01); `extra="forbid"` and `TOLERATED_SCHEMA_ERRORS` are unchanged.
- All docstrings (module + both helpers) were corrected to match the code, including `coerce_mapping_list`'s different `extra="forbid"` failure route.

## Task Commits

Each task was committed atomically:

1. **Task 1: failure-class tests (RED)** - `35d29b8` (test)
2. **Task 2: key-restricted, bounded unwrap + docstrings (GREEN)** - `7a5629d` (fix)
3. **Task 3: TailoringPatch list-field wiring (IN-01)** - `f2cf1a7` (feat)

**Plan metadata:** (docs commit, below)

## Files Created/Modified

- `app/domain/schemas/_coerce.py` - `WRAPPER_KEY` constant; key-restricted, self-reference-bounded unwrap; docstrings state the key restriction and the two failure routes.
- `app/domain/cv.py` - `_coerce_ops` / `_coerce_gaps` / `_coerce_suggestions` before-validators on `TailoringPatch`; `coerce_mapping_list` import; purity docstring unchanged (both imports come from the same pure sibling).
- `tests/domain/test_coerce.py` - failure-class cases, the `coerce_mapping_list` `extra="forbid"` route case, the `TailoringPatch` wrapper/bare-object cases, the self-referential-termination case ordered last.
- `tests/domain/test_screening_schema.py` - `test_an_unrecognised_mapping_evidence_ids_still_fails_loudly` rewritten to a list-value class input.

## Decisions Made

- Chose reviewer option (i): restrict the unwrap to the literal key, which makes the documented behaviour true and restores the fail-closed posture, rather than re-describing a wider acceptance.
- IN-02 closed in the same edit (`inner is value` break); IN-01 closed via wiring only, no duplicated coercion logic in `cv.py`.
- `coerce_mapping_list`'s docstring states its own failure route (`extra="forbid"`) instead of repeating the `list_type` reasoning (CONVENTIONS rule 6).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Task 2's declared verify command cannot pass before Task 3**
- **Found during:** Task 2 (the RED tests committed in Task 1 include the IN-01 `TailoringPatch` cases, but the `coerce_mapping_list` wiring that makes them green lands in Task 3).
- **Issue:** Task 2's `<verify>` command includes `tests/domain/test_coerce.py -x`; with `-x` the run halts on the first `TailoringPatch` case — its target is Task 3, so the declared gate cannot exit 0 until Task 3 is done.
- **Fix:** Ran Task 2's gate on the same file set with `-k "not tailoring_patch"` (54 passed, 4 deselected, ruff clean), which is exactly the helper-scoped portion Task 2 owns; the full unde-selected combined gate was then run and passed at Task 3 (131 passed). The excluded tests are Task 3's declared target, not Task 2's.
- **Files modified:** none beyond the plan's Task 2/3 files.
- **Verification:** post-Task-2 deselected lane 54 passed; post-Task-3 combined lane 131 passed; full default lane 1706 passed, 14 deselected, 2 xfailed.
- **Committed in:** `7a5629d` (Task 2 commit); the tests themselves in `35d29b8`.

---

**Total deviations:** 1 auto-fixed (1 blocking, a plan verify-command sequencing defect)
**Impact on plan:** No scope creep; the fix is confined to how Task 2's gate was run, not to any code change.

## Issues Encountered

- Sandbox interpreter: `.venv/bin/python` is a broken Python 3.14 venv, so the declared commands were run with the provisioned `/tmp/opencode/gsdvenv13/bin/python` (3.13.16, pytest 9.1.1) exactly as the plan's environment note anticipated; `.venv/bin/python -m pytest` remains the command of record.
- RED evidence: on the pre-fix helper `unwrap_single_key_mapping({"nope": ["bul/x/1"]})` returned `['bul/x/1']` (the defect); `ScreeningAnswer` with `evidence_ids={"nope": ["bul/x/1"]}` validated (DID NOT RAISE); the `TailoringPatch` wrapper cases raised `list_type`; and the self-referential case hung (timeout exit 124).
- Full default lane: **1706 passed, 14 deselected, 2 xfailed** (314.36s).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- WR-01 closed at the coercion boundary; `TOLERATED_SCHEMA_ERRORS` untouched; no new dependency; no migration; no schema-send change.
- Criterion-E style closure (does the prose match the behaviour?) is owned by the phase's independent review/verification, not this fix author (CONVENTIONS rule 5) — recorded as coverage D4 with `human_judgment: true`.

---
*Phase: 07-assisted-apply-tracker*
*Completed: 2026-10-12*

## Self-Check: PASSED

- Files exist: `app/domain/schemas/_coerce.py`, `app/domain/cv.py`, `tests/domain/test_coerce.py`, `tests/domain/test_screening_schema.py`, `07-14-SUMMARY.md`.
- Commits exist: `35d29b8`, `7a5629d`, `f2cf1a7`.
