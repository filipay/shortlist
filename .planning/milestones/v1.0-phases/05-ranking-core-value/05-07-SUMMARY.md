---
phase: 05-ranking-core-value
plan: 07
subsystem: ui
tags: [fastapi, jinja2, sqlalchemy, ranking, read-model, queue]

requires:
  - phase: 05-ranking-core-value
    provides: "05-05's ranking-strip denominator (RunSummary.candidate_count) and its two strip tests"
provides:
  - "A non-positive persisted candidate count degrades to None at the run read boundary"
  - "The queue #ranking-strip ratio branch requires a truthy denominator"
  - "First-class regression coverage for the ranked_count=5, survivors=0 state (05-VERIFICATION.md must-have truth #24)"
affects: [phase-05-verification, phase-06-tailoring, queue-ui]

actuals:
  tokens: 1357
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "A denominator read from persistence is validated positive at the read boundary, not at the render site"

key-files:
  created: []
  modified:
    - app/db/repositories/run_repo.py
    - app/web/templates/html/queue.html
    - tests/api/test_queue_ranked.py

key-decisions:
  - "Excluded a non-positive candidate count at the run read boundary (run_repo._optional_int), not by omitting survivors in app/pipeline/run.py — the read boundary covers the fabricated failure path, a hand-edited row and an older-build row alike."
  - "Tightened the template ratio gate to a truthiness test as deliberate defence in depth at the site that makes the claim."
  - "Left app/pipeline/run.py's latent survivors:0 payload untouched: invisible to this surface after the fix, and route (b) would widen the blast radius for no user-visible gain."

patterns-established:
  - "Read-boundary exclusion: a value the UI divides by is normalised to None when unusable, so every producer degrades identically."

requirements-completed: [UI-01, RANK-08]

coverage:
  - id: D1
    description: "RunSummary.candidate_count is None for a persisted zero or negative survivors count"
    requirement: UI-01
    verification:
      - kind: unit
        ref: "tests/api/test_queue_ranked.py#test_run_summary_has_no_candidate_count_for_a_non_positive_survivors"
        status: pass
    human_judgment: false
  - id: D2
    description: "GET / renders `Ranked 5` and never `Ranked 5 of 0` for a run with ranked_count=5 and survivors=0"
    requirement: UI-01
    verification:
      - kind: integration
        ref: "tests/api/test_queue_ranked.py#test_ranking_strip_with_zero_candidate_count_renders_no_ratio"
        status: pass
    human_judgment: false
  - id: D3
    description: "The positive and absent-count strip behaviours shipped by 05-05 stay green"
    requirement: RANK-08
    verification:
      - kind: integration
        ref: "tests/api/test_queue_ranked.py#test_ranking_strip_reports_the_runs_own_candidate_count"
        status: pass
      - kind: integration
        ref: "tests/api/test_queue_ranked.py#test_ranking_strip_without_candidate_count_renders_no_ratio"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-09-22
status: complete
---

# Phase 5 Plan 07: Ranking strip — a zero candidate population is not a denominator

**The queue's "Ranked X of Y" strip can no longer print a ratio against a fabricated zero: a non-positive persisted candidate count degrades to `None` at the run read boundary, the ratio branch requires a truthy denominator, and two first-class tests pin the `ranked_count=5, survivors=0` state.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-09-22T17:16:00Z
- **Completed:** 2026-09-22T17:25:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Closed the one remaining FAILED must-have truth (#24 in `05-VERIFICATION.md`): `Ranked 5 of 0` is now impossible on the queue page.
- Tightened `run_repo._optional_int` to return `None` for a zero or negative parsed value, so `RunSummary.candidate_count` is unusable rather than `0` — the exclusion sits at the read boundary and therefore holds for every producer (the pipeline's bookkeeping-failure path, a hand-edited row, an older-build row).
- Changed the `queue.html` `#ranking-strip` ratio gate from `is not none` to a truthiness test as defence in depth at the render site, and updated the surrounding comment to say a non-positive count is treated as absent.
- Added `test_ranking_strip_with_zero_candidate_count_renders_no_ratio` and `test_run_summary_has_no_candidate_count_for_a_non_positive_survivors`, pinning both the rendered strip and the read model.
- Kept the positive (`Ranked 5 of 30`) and absent-count (`Ranked 5`) behaviours shipped by 05-05 green.

## Task Commits

Each task was committed atomically:

1. **Task 1: A non-positive candidate count is not a denominator — at the read boundary and at the render site** - `4948676` (fix)
2. **Task 2: Pin the zero denominator with a first-class regression test** - `236c086` (test)

**Plan metadata:** `pending` (docs: complete plan)

_Note: no TDD tasks in this plan._

## Files Created/Modified
- `app/db/repositories/run_repo.py` - `_optional_int` returns `parsed if parsed > 0 else None`; docstring states a denominator must be positive.
- `app/web/templates/html/queue.html` - `#ranking-strip` ratio branch gated on `{% if ranking_strip.get('candidates') %}`; comment updated.
- `tests/api/test_queue_ranked.py` - two regression tests plus `from app.db.repositories import run_repo`.

## Decisions Made
- **Route (a), the read boundary** — `run_repo._optional_int` — over route (b), omitting `survivors` from `app/pipeline/run.py`'s bookkeeping-failure payload. Route (b) fixes only the one producer and would leave the hand-edited row, the older-build row and the required regression test failing; the read-boundary exclusion covers all three with a two-line change.
- **Truthiness gate at the render site** is deliberate defence in depth: after the read-boundary fix an `is not none` test would be correct, but the truthiness test means a future hand-built strip context with a `0` still cannot print the ratio.
- **`app/pipeline/run.py` left unchanged** — the latent fabricated `survivors: 0` is invisible to this surface after the fix (WR-06 closed), and route (b) would widen the blast radius on `_assemble_run_reason`'s other consumers for no additional user-visible gain.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. The full default-lane suite (1048 passed, 14 deselected, 2 xfailed) and the targeted queue/run suites (22 passed) are green.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Must-have truth #24 is closed; the queue strip can no longer print a ratio against a non-positive or fabricated denominator.
- No migration, schema change, new package or CDN asset; Alembic head stays `0004`.
- Ready for Phase 5 re-verification.

---
*Phase: 05-ranking-core-value*
*Completed: 2026-09-22*

## Self-Check: PASSED

All declared files exist and both task commits (`4948676`, `236c086`) are present.
