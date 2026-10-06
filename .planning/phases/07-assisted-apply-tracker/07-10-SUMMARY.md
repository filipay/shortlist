---
phase: 07-assisted-apply-tracker
plan: 10
subsystem: api
tags: [fastapi, screening, drafts, data-integrity, pytest]

requires:
  - phase: 07-assisted-apply-tracker
    provides: the `POST /listings/{id}/apply/draft` route, `ground_screening_answers`, and `screening_draft_repo.replace_for_listing`
provides:
  - a `len(verdicts) < len(questions)` completeness guard returning `drafting_partial` before any draft row is replaced
  - the CR-01 regression locking survival of unanswered/ad-hoc stored drafts
affects: [07-verify-work, apply-package drafting]

tech-stack:
  added: []
  patterns:
    - "Fail-closed pre-write completeness guard: refuse a short model response before the wholesale DELETE, rather than trusting the model to cover every asked question"

key-files:
  created: []
  modified:
    - app/api/apply.py
    - tests/api/test_apply_package.py
    - tests/api/test_apply_draft_errors.py

key-decisions:
  - "CR-01: treat `len(verdicts) < len(questions)` as its own refusal (`drafting_partial`, 502) placed before `replace_for_listing`, because `ground_screening_answers` emits one verdict per answer via positional `zip(..., strict=False)`"
  - "The two prior one-answer package tests were updated to complete four-answer responses so no test enshrines partial-response data loss"

patterns-established:
  - "A wholesale replace-on-success path must be gated by an explicit response-completeness check; a non-empty partial list is not success"

requirements-completed: [APPLY-01]

coverage:
  - id: D1
    description: "A valid-but-partial drafting response is refused with `drafting_partial` (502) before any draft row is deleted; seeded ad-hoc rows and their question_text survive."
    requirement: APPLY-01
    verification:
      - kind: unit
        ref: "tests/api/test_apply_draft_errors.py#test_a_partial_response_keeps_unanswered_ad_hoc_rows"
        status: pass
      - kind: unit
        ref: "tests/api/test_apply_draft_errors.py#test_a_repeated_partial_post_is_idempotent_over_the_stored_set"
        status: pass
    human_judgment: false
  - id: D2
    description: "A complete response (one answer per asked question) still returns 200 and persists the full asked answer set — the guard does not over-refuse."
    requirement: APPLY-01
    verification:
      - kind: unit
        ref: "tests/api/test_apply_draft_errors.py#test_a_complete_response_persists_the_full_asked_set"
        status: pass
      - kind: unit
        ref: "tests/api/test_apply_package.py#test_the_draft_action_makes_one_call_and_persists_rows"
        status: pass
    human_judgment: false

actuals:
  tokens: 3449
  tasks: 2
  commits: 2

duration: 8min
completed: 2026-10-06
plan_head_before: 593df3ee6d4963ee8dc77b1f12075d0a5c8977cd
status: complete
---

# Phase 07 Plan 10: CR-01 partial-drafting-response Data-Loss Summary

**A `drafting_partial` refusal that returns before `screening_draft_repo.replace_for_listing`, so a valid-but-short model response can no longer DELETE the user's unanswered and ad-hoc stored drafts.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-06T20:38:21Z
- **Completed:** 2026-10-06T20:46:13Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Closed CR-01: `draft_answers` now refuses a valid-but-partial response (`len(verdicts) < len(questions)`) with `data-error="drafting_partial"` (502) **before** the wholesale DELETE inside `replace_for_listing` is reached, keeping every stored row, including ad-hoc question text that exists nowhere else.
- Documented the third 502 refusal in the `draft_answers` docstring (alongside `drafting_failed`/`drafting_empty`) and named the positional `zip(..., strict=False)` mechanism in an inline comment.
- Converted the two one-answer `test_apply_package.py` stubs to complete four-answer responses, so no test enshrines a partial-response delete; the WR-04 reworded-question intent is preserved.
- Added the verifier's exact 3-rows→1 reproduction as a passing regression, plus a complete-path boundary check and an APPLY-01 repeated-POST idempotency check.

## Task Commits

Each task was committed atomically:

1. **Task 1: Refuse a partial drafting response before any draft row is replaced** - `0c01ab2` (fix)
2. **Task 2: Regression — seed ad-hoc rows, return a partial response, assert they survive** - `94c3421` (test)

**Plan metadata:** (final docs commit, below)

## Files Created/Modified
- `app/api/apply.py` - added the `len(verdicts) < len(questions)` guard returning `drafting_partial` before `replace_for_listing`; documented the third refusal in the docstring
- `tests/api/test_apply_package.py` - the two named tests now stub one answer per asked `DEFAULT_QUESTIONS` entry (four answers) and assert the full asked set persists
- `tests/api/test_apply_draft_errors.py` - three new tests: partial-response survival of three seeded ad-hoc rows, complete-path persistence of the full asked set, and repeated-partial-POST idempotency

## Verification

- Combined gate: `.venv/bin/python -m pytest -q tests/api/test_apply_package.py tests/api/test_apply_draft_errors.py -x` → **33 passed** (baseline before the change was 30 passed).
- `tests/api/test_apply_draft_errors.py` alone → **6 passed**.
- Adjacent lanes: `tests/verify/test_screening.py tests/pipeline/test_draft_stage.py tests/db/test_screening_draft_repo.py tests/api/test_apply_package_warnings.py tests/domain/test_screening_schema.py` → **55 passed**.
- Acceptance literals: `app/api/apply.py` contains `len(verdicts) < len(questions)` (L356) and `drafting_partial` (L358), and the `drafting_partial` branch textually precedes `await screening_draft_repo.replace_for_listing(` (L364).
- The `drafting_failed` / `drafting_empty` branches, the unconditional pre-refusal `session.commit()`, and the complete-path `replace_for_listing` call are unchanged.

## Decisions Made
- **CR-01 guard placement:** refuse before the write path rather than making `replace_for_listing` an upsert-by-question. The plan's primary option (a distinct refused outcome) was chosen: it is the smaller, fail-closed diff and preserves the shipped "replace the whole set on a complete success" contract.
- **Completeness predicate:** `len(verdicts) < len(questions)` is exactly a partial response because `ground_screening_answers` aligns positionally over a `zip(..., strict=False)`, so it can never emit more verdicts than answers.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CR-01 is closed; `verify-phase 07` can re-run and expect the 3-rows→1 reproduction to pass.
- The two non-inferable backstop truths preserved by the prior verification (tracker note `title` fidelity, clipboard multi-paragraph copy fidelity) remain `PRESENT_BEHAVIOR_UNVERIFIED` and are untouched by this plan.

---
*Phase: 07-assisted-apply-tracker*
*Completed: 2026-10-06*

## Self-Check: PASSED

- Found: `app/api/apply.py`
- Found: `tests/api/test_apply_package.py`
- Found: `tests/api/test_apply_draft_errors.py`
- Found: `.planning/phases/07-assisted-apply-tracker/07-10-SUMMARY.md`
- Found commit: `0c01ab2` (fix: refuse partial drafting response)
- Found commit: `94c3421` (test: CR-01 regression)
