---
phase: 06-tailoring-verification
plan: 05
subsystem: testing
tags: [verification, metric-containment, pypdf, region-scoping, pydantic]

requires:
  - phase: 06-tailoring-verification
    plan: 02
    provides: the Layer-2 check set, the metric tokeniser and `region_token_report`
provides:
  - "region-local check-4 exclusion: an entry's OWN date cores, page-number lines inside the region, and the non-entry structured strings that physically appear in it"
  - "`non_entry_structured_strings(plan)` + `_region_structured_cores(plan, region_text)` in app/verify/numbers.py"
  - "VERIFIER_VERSION 1.0.1 recording the check-4 change"
  - "tests/fixtures/verify/digit_skill_extract.txt and `with_digit_skill(...)` proving a digit-bearing ordinary skill label passes while the novel-metric negative control still fails"
affects: [06-06, 06-07, 07-apply-and-track]

actuals:
  tokens: 4037
  tasks: 2
  # 2 task commits + this plan's metadata commit.
  commits: 2
  plan_head_before: ac6aa7459e25a50167e33eaa3c541eb18e99fc35

tech-stack:
  added: []
  patterns:
    - "region-local exclusion: a structured token is excused only where its string physically appears, never document-wide"
    - "the module-level pure-helper idiom of app/domain/sanitize.py (total, deterministic, clock-free, no I/O)"

key-files:
  created:
    - tests/fixtures/verify/digit_skill_extract.txt
  modified:
    - app/verify/numbers.py
    - app/verify/base.py
    - tests/verify/fixtures.py
    - tests/verify/test_numbers.py
    - tests/verify/test_text_checks.py

key-decisions:
  - "GAP 1 (CR-01) fixed with the third, stricter form: exclude the plan's non-entry structured content only in the region whose text physically contains that string — not a global union (which would silence a fabricated digit that equals a skill label's digit) and not a heading bound (the template renders a section's skills table AFTER its last entry, so a heading bound would not exclude them)"
  - "WR-03 closed by making the date-like exclusion per-region: an entry's OWN date cores only, never the union of every entry's dates"
  - "Page-number exclusion is region-local too — a lone-integer line excuses its value only inside the region that contains the line"
  - "VERIFIER_VERSION bumped 1.0.0 -> 1.0.1 as provenance, not a migration: no column, table or Alembic revision changes; previously persisted verification_json rows keep the version they were written with"
  - "No blocking check was weakened or deleted: passed remains `no check has status \"fail\"`, metric_containment stays a hard fail, page_budget/layout_ats stay the only warn-only checks"

patterns-established:
  - "The plan strings no entry owns (identity block, section titles, skill groups/labels) are read through one helper, `non_entry_structured_strings`, so a future field is added in one place"
  - "A false positive is fixed by correcting the region and allow-set construction in the shared path, never by excusing the token document-wide"

requirements-completed: [TAIL-04]

coverage:
  - id: D1
    description: "Check-4 region and allow-set construction is region-local: an entry's own dates, in-region page numbers, and the non-entry structured strings that physically appear in the region"
    requirement: TAIL-04
    verification:
      - kind: unit
        ref: "tests/verify/test_numbers.py::test_a_foreign_date_core_is_not_excluded_in_another_region"
        status: pass
      - kind: unit
        ref: "tests/verify/test_numbers.py::test_a_digit_in_a_skill_label_appearing_in_the_region_is_not_a_candidate"
        status: pass
    human_judgment: false
  - id: D2
    description: "A valid tailored CV whose Skills block carries a digit-bearing ordinary label passes metric_containment end-to-end, while a genuinely novel metric token still fails"
    requirement: TAIL-04
    verification:
      - kind: unit
        ref: "tests/verify/test_text_checks.py::test_a_digit_bearing_skill_label_still_passes_metric_containment"
        status: pass
      - kind: unit
        ref: "tests/verify/test_text_checks.py::test_a_novel_metric_token_fails_metric_containment"
        status: pass
      - kind: unit
        ref: "tests/verify/test_numbers.py::test_the_committed_digit_skill_extract_has_no_surplus_candidate"
        status: pass
    human_judgment: false
  - id: D3
    description: "VERIFIER_VERSION records the check-4 change so a persisted outcome traces to the check revision that produced it"
    requirement: TAIL-04
    verification:
      - kind: unit
        ref: "tests/verify/test_text_checks.py::test_a_valid_extraction_passes_every_layer_two_check (asserts result.verifier_version == VERIFIER_VERSION)"
        status: pass
    human_judgment: false

duration: 9
completed: 2026-09-24
status: complete
---

# Phase 06 Plan 05: GAP 1 + WR-03 Summary

**Check-4 metric containment is region-local: a digit-bearing Skills block no longer hard-blocks an otherwise valid CV, and one entry's dates can no longer excuse a token in another entry's region**

## Performance

- **Duration:** 9 min
- **Started:** 2026-09-24T22:27:19Z
- **Completed:** 2026-09-24T22:36:00Z
- **Tasks:** 2
- **Files modified:** 6 (1 created)

## Accomplishments

- The false positive that made preview and download dead for any CV whose trailing structured content carries a digit is fixed at the shared path: `region_token_report` now excludes an entry's OWN date cores, in-region page-number lines, and the digit cores of the plan's non-entry structured strings **only in the region whose extracted text physically contains that string**.
- WR-03 is closed: the document-wide union of every entry's date cores (and the document-wide page-number scan) is deleted, so a token equal to another entry's year is a candidate again inside a region that does not contain that entry.
- `VERIFIER_VERSION` is bumped to `1.0.1` — the observable trace from the check-4 change back to a persisted `verification_json` outcome.
- A committed digit-bearing extraction (`digit_skill_extract.txt`) plus `with_digit_skill(...)` prove a valid CV passes end-to-end, while `novel_metric_extract.txt` (`Python 3.12`) still fails `metric_containment` with `exp/northwind-labs-2021:3.12` — the true positive is intact.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end — a digit-bearing Skills block no longer blocks an otherwise valid CV** - `6e066ce` (fix)
2. **Task 2: The committed digit-bearing skill fixture and the containment proof** - `97c718d` (test)

**Plan metadata:** (this SUMMARY commit)

## Files Created/Modified

- `app/verify/numbers.py` - added `non_entry_structured_strings` and `_region_structured_cores`; rewrote the per-region loop so date, page-number and structured exclusion are all region-local; deleted the two document-wide pre-loops; updated the module docstring and `__all__`
- `app/verify/base.py` - `VERIFIER_VERSION` `"1.0.0"` -> `"1.0.1"`
- `tests/verify/fixtures.py` - added `with_digit_skill(...)`; `build_fixture` gained a `facts=` keyword; `__all__` updated
- `tests/fixtures/verify/digit_skill_extract.txt` - the committed digit-bearing Skills extraction (`infrastructure AWS S3`), byte-identical to `base_extract.txt` otherwise
- `tests/verify/test_numbers.py` - `test_a_foreign_date_core_is_not_excluded_in_another_region`, `test_a_digit_in_a_skill_label_appearing_in_the_region_is_not_a_candidate`, `test_the_committed_digit_skill_extract_has_no_surplus_candidate`
- `tests/verify/test_text_checks.py` - `test_a_digit_bearing_skill_label_still_passes_metric_containment`

## Decisions Made

- **GAP 1 fix-contract choice, stated explicitly:** the plan took the third, stricter form — excluding non-entry structured content only where its string physically appears in the region. A document-wide union was rejected because it would silence check 4 for a fabricated digit that happens to equal a skill label's digit (the WR-03 false-negative class); a heading bound was rejected because the template renders a section's skills table AFTER its last entry, so a heading bound would not exclude a section carrying both entries and skills. Neither alternative changes a check or a severity.
- **`_region_structured_cores` stays region-local** and is documented as such: a structured token is excused only in the region whose text physically contains the string.
- **`VERIFIER_VERSION` is provenance, not identity:** bumped to `1.0.1` rather than treated as a migration; the Alembic head stays `0004` and previously persisted rows keep their written version.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The full hermetic lane passes (1225 passed, 14 deselected, 2 xfailed — up 4 from the pre-plan 1221, matching the four new tests). `.venv/bin/python -m compileall -q app` is clean. `tests/verify tests/pipeline/test_tailor_stage.py` (66) and `tests/test_import_discipline.py` (9) are green.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- GAP 1 (CR-01, BLOCKER) and WR-03 are closed; TAIL-04's remaining gap-closure work concerns only the WR-02 bullet-id grounding in `06-06`.
- Alembic head unchanged at `0004`; no migration, setting or dependency added.
- The negative control (`novel_metric_extract.txt`) is untouched, so a future regression that blanket-excuses digits in a Skills block fails loudly.

---

*Phase: 06-tailoring-verification*
*Completed: 2026-09-24*

## Self-Check: PASSED

- FOUND: `tests/fixtures/verify/digit_skill_extract.txt`
- FOUND: `6e066ce` (Task 1 commit)
- FOUND: `97c718d` (Task 2 commit)
