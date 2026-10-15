---
phase: 06-tailoring-verification
plan: 06
subsystem: domain
tags: [patch-engine, validation, pydantic, change-log, audit-integrity]

requires:
  - phase: 06-tailoring-verification
    plan: 01
    provides: the typed patch engine, `_validate_patch`, `_build_plan` and `_change_for`
provides:
  - "per-op-family grounding in `_validate_patch`: bullet ops resolve against `bullet_ids`, `ReorderSection` against `section_ids`"
  - "no phantom `ChangeRecord` from a non-bullet / non-section id (WR-02 closed)"
  - "a change-log honesty pin: every record names a real source fact at its op family's own locus"
affects: [06-05, 06-07]

actuals:
  tokens: 1857
  tasks: 2
  # 2 task commits + this plan's metadata commit.
  commits: 2
  plan_head_before: 33f9bedcb14c9ddc792aa6eaf59200e7ef1dd1da

tech-stack:
  added: []
  patterns:
    - "ground an op's id fields against the id set of the op's OWN family at the single validation boundary"
    - "a change-log entry is validated by locus (drop names a removed source bullet; the rest name plan entities), not by a structural op-count equality"

key-files:
  created: []
  modified:
    - app/domain/cv.py
    - tests/domain/test_patch_ops.py

key-decisions:
  - "GAP 2 (WR-02) fixed at the single grounding decision point: `_validate_patch` selects the grounding set per op family, so a rejected op raises `UnknownIdError` before `_build_plan` runs and no `ChangeRecord` is emitted"
  - "`ReorderSection.section_id` is grounded on the section-id set too — the identical phantom-change class in the other op family, inside GAP 2's truth ('a change-log entry always describes a change that actually occurred')"
  - "Valid-id no-ops (a move before itself, a reweight to the current weight) are deliberately NOT reclassified: the honesty invariant is per-op-locus (a record names a real source fact of its family's kind at the right locus), not 'every record changed the output'"
  - "Gap and suggestion references keep the full `known_ids` grounding — they are audit-only and never applied, so no phantom change can arise from them"
  - "No stored patch is invalidated: D-109 does not persist a generated patch, and `cv_artifacts.patch_json` is written only for a patch that already passed validation; the Alembic head stays 0004"

patterns-established:
  - "The validation boundary is the only place an op family's grounding set is decided; no post-hoc filter in `_build_plan` or `_change_for`"
  - "A change-log honesty test asserts locus per op family, with a drop provably absent from the built plan"

requirements-completed: [TAIL-08]

coverage:
  - id: D1
    description: "A bullet-targeting op (move/reweight/demote/drop) resolves `bullet_id` and `before_id` against the bullet-id set, so a skill/section/entry/org/title/gap id raises `UnknownIdError`"
    requirement: TAIL-08
    verification:
      - kind: unit
        ref: "tests/domain/test_patch_ops.py::test_a_bullet_op_on_a_non_bullet_fact_id_raises"
        status: pass
      - kind: unit
        ref: "tests/domain/test_patch_ops.py::test_an_unknown_id_raises_unknown_id_error"
        status: pass
    human_judgment: false
  - id: D2
    description: "`ReorderSection.section_id` resolves against the section-id set, so a non-section id raises `UnknownIdError` instead of no-opping into a record"
    requirement: TAIL-08
    verification:
      - kind: unit
        ref: "tests/domain/test_patch_ops.py::test_a_reorder_section_on_a_non_section_id_raises"
        status: pass
      - kind: unit
        ref: "tests/domain/test_patch_ops.py::test_reorder_section_moves_the_section_and_records_the_new_order"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every `ChangeRecord` from a valid five-op patch names a real source fact at its op family's locus: a drop names a removed source bullet; reweight/demote/move name plan bullets; a section record names a plan section"
    requirement: TAIL-08
    verification:
      - kind: unit
        ref: "tests/domain/test_patch_ops.py::test_every_change_record_describes_an_effect_at_the_right_locus"
        status: pass
    human_judgment: false

duration: 12
completed: 2026-09-24
status: complete
---

# Phase 06 Plan 06: GAP 2 Summary

**A bullet or section op can no longer name a non-bullet/non-section fact id and record a phantom change: op ids are grounded against their own family's id set at the single validation boundary**

## Performance

- **Duration:** 12 min
- **Started:** 2026-09-24T22:41:07Z
- **Completed:** 2026-09-24T22:53:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `_validate_patch` now selects its grounding set per op family instead of one generic `known_ids` pass: the four bullet ops (`BulletMove`, `BulletWeight`, `DemoteBullet`, `DropBullet`) resolve `bullet_id`/`before_id` against `bullet_ids`, and `ReorderSection` resolves `section_id` against `section_ids`.
- The phantom change is unreachable: a non-bullet/non-section id raises `UnknownIdError` from `_validate_patch`, which `apply_patch` calls **before** `_build_plan`, so no `RenderPlan` and no `ChangeRecord` is produced (D-106 all-or-nothing preserved).
- Change-log honesty is pinned: for a valid five-op patch, a `drop_bullet` record names a source bullet the built plan no longer carries, and `reweight`/`demote`/`move`/`reorder_section` records name entities the plan carries. A second change-log builder was not added (`_change_for` still appears once); no post-hoc filter was added.
- Gap and suggestion reference grounding is unchanged (full fact-id set) — they are audit-only, so no phantom change arises from them.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end — a bullet op naming a non-bullet id is rejected at the boundary** - `1ce3972` (fix)
2. **Task 2: The section-targeting op and the change-log honesty pin** - `70fcdc3` (fix)

**Plan metadata:** (this SUMMARY commit)

## Files Created/Modified

- `app/domain/cv.py` - `_validate_patch` gains `bullet_ids` and `section_ids`; the generic `known_ids` pass over `patch.ops` is replaced by a per-op-family grounding selection (bullets for the four bullet ops, sections for `ReorderSection`, `known_ids` for any future op); the docstring now states the per-family contract
- `tests/domain/test_patch_ops.py` - `test_a_bullet_op_on_a_non_bullet_fact_id_raises`, `test_a_reorder_section_on_a_non_section_id_raises`, `test_every_change_record_describes_an_effect_at_the_right_locus`

## Decisions Made

- **GAP 2 (WR-02) fixed at the single grounding decision point**, not at each call site: the validation boundary is the only place an op family's grounding set is decided; no filter in `_build_plan` or `_change_for` papers over an unsound id.
- **`ReorderSection.section_id` grounded on sections too** — the same phantom-change class in the other op family. Forbidding an op family and leaving the sibling is the same defect with a smaller blast radius.
- **Valid-id no-ops deliberately stay**: `move_bullet(X, before_id=X)` and a reweight to a bullet's current weight remain valid and still record, because their record names a fact the plan genuinely carries. The honesty invariant is per-op-locus, NOT "every record changed the output" — the latter is not a property the shipped engine has.
- **No stored row is invalidated**: D-109 does not persist a generated patch and `cv_artifacts.patch_json` is written only for a patch that already passed validation, so no retro-migration is needed; the Alembic head stays `0004`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The full hermetic lane passes (1228 passed, 14 deselected, 2 xfailed — up 3 from the pre-plan 1225, matching the three new tests). `.venv/bin/python -m compileall -q app` is clean and `ruff check` passes on both modified files. The targeted lanes `tests/domain/test_patch_ops.py tests/domain/test_cv_ids.py tests/test_import_discipline.py` and the full `tests/api` suite are green.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- GAP 2 (WR-02) is closed. TAIL-08's drop/demote reason rendering was already shipped in 06-03; the remaining FLAGGED edge (whether a suggestion or unapplied gap should appear in the same change log) is unchanged and out of this plan's scope.
- Alembic head unchanged at `0004`; no migration, setting or dependency added.
- Validation remains all-or-nothing and raises; a rejected patch writes no artifact.

---

*Phase: 06-tailoring-verification*
*Completed: 2026-09-24*

## Self-Check: PASSED

- FOUND: `1ce3972` (Task 1 commit)
- FOUND: `70fcdc3` (Task 2 commit)
- Confirmed: `grep -c "def _change_for" app/domain/cv.py` → 1 (no second change-log builder)
