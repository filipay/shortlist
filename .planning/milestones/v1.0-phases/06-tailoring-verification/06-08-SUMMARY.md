---
phase: 06-tailoring-verification
plan: 08
subsystem: testing
tags: [verifier, metric-containment, region-segmentation, cr-01, cr-02, tail-04]

requires:
  - phase: 06-tailoring-verification
    provides: "Layer-2 check 4 (metric_containment) region-local exclusion and the 06-05 verifier idiom"
provides:
  - "check 4 grounds an entry's location digit cores in its own region allowed set (CR-01 closed)"
  - "each region is anchored on its own entry header line (org AND title), so a bullet naming a later employer cannot bleed digits across regions (CR-02 closed)"
  - "VERIFIER_VERSION 1.0.2 records the combined CR-01 + CR-02 check change"
  - "committed digit_location_extract.txt fixture + with_digit_location builder"
affects: [06-09, phase-07-application-tracker, verifier-future-changes]

actuals:
  tokens: 3253
  tasks: 2
  commits: 2
  plan_head_before: d18d435f47dd80b7263064f22f73a23068479a1a

tech-stack:
  added: []
  patterns:
    - "allowed-set grounding: a region's allow-list enumerates every source token the region renders; new fields join `allowed` only, never `excluded`"
    - "header anchoring: a region starts on the line carrying the entry's org AND title, not a bare org substring"

key-files:
  created:
    - tests/fixtures/verify/digit_location_extract.txt
  modified:
    - app/verify/numbers.py
    - app/verify/base.py
    - tests/verify/fixtures.py
    - tests/verify/test_numbers.py
    - tests/verify/test_text_checks.py

key-decisions:
  - "The location digit core is added to the entry's OWN `allowed` set only, never to `excluded`: the digit stays a region candidate and is grounded by membership, mirroring the 06-05 skill-label asymmetry"
  - "A region is anchored on a line carrying BOTH squash(org) AND squash(title) — the template emits both on one header line (cv.tex.jinja:58) — rather than an org-only substring, which is exactly the CR-02 defect"
  - "A split org/title header is reported found=False (check 4 skips it) rather than mis-located at a bullet; the deliberate trade-off is pinned by test_a_split_header_entry_is_reported_not_found_not_mislocated"
  - "VERIFIER_VERSION is bumped ONCE to 1.0.2 for the combined CR-01 + CR-02 change; Task 2 changes _entry_lines under that same version and does not bump again"

patterns-established:
  - "A docstring that enumerates an allow-set's source fields must name every field (IN-07): the miss of `location` was what let CR-01 through review"
  - "Every region start/end behaviour change is pinned by both a positive and a negative-control test (the novel_metric_extract Python 3.12 control stays untouched)"

requirements-completed: [TAIL-04]

coverage:
  - id: D1
    description: "A tailored CV whose rendered entry location carries a digit (Dublin 2) verifies: the location digit core is in the region's allowed set, no surplus candidate is computed, and check 4 returns pass"
    requirement: "TAIL-04"
    verification:
      - kind: unit
        ref: "tests/verify/test_numbers.py#test_a_digit_bearing_location_is_not_a_surplus_candidate"
        status: pass
      - kind: unit
        ref: "tests/verify/test_text_checks.py#test_a_digit_bearing_location_still_passes_metric_containment"
        status: pass
    human_judgment: false
  - id: D2
    description: "Each experience region anchors on its own entry header line, so an earlier entry's bullet naming a later employer does not start the later region or bleed its digits across"
    requirement: "TAIL-04"
    verification:
      - kind: unit
        ref: "tests/verify/test_numbers.py#test_a_bullet_naming_a_later_employer_does_not_bleed_into_its_region"
        status: pass
    human_judgment: false
  - id: D3
    description: "The committed digit_location_extract.txt fixture passes end-to-end and the split-header extraction variation is pinned as a visible found=False decision; the Python 3.12 novel-metric negative control still fails"
    requirement: "TAIL-04"
    verification:
      - kind: unit
        ref: "tests/verify/test_numbers.py#test_the_committed_digit_location_extract_has_no_surplus_candidate"
        status: pass
      - kind: unit
        ref: "tests/verify/test_numbers.py#test_a_split_header_entry_is_reported_not_found_not_mislocated"
        status: pass
      - kind: unit
        ref: "tests/verify/test_text_checks.py#test_a_novel_metric_token_fails_metric_containment"
        status: pass
    human_judgment: false

duration: 8 min
completed: 2026-09-25
status: complete
---

# Phase [6] Plan [08]: CR-01 + CR-02 — check 4 grounds an entry's location and anchors each region on its own header

**Layer-2 check 4 (`metric_containment`) now grounds an entry's digit-bearing location in that entry's own region and anchors each region on its own org-AND-title header line, so ordinary valid CVs verify, preview and download again — while a genuinely novel metric token still hard-fails.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-09-25T08:59:24Z
- **Completed:** 2026-09-25T09:07:21Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- `_allowed_for_entry` folds `entry.location` digit cores into the entry's own `allowed` set (allowed-only, never `excluded`), closing CR-01 — a location like `Dublin 2` is a region candidate grounded by membership, not a surplus that hard-fails.
- `_entry_lines` anchors each region on the line carrying BOTH `squash(org)` and `squash(title)`, closing CR-02 — a bullet naming a later employer can no longer start that employer's region and donate its digits; the last region still runs to end-of-text (the WR-03 / 06-05 property).
- `VERIFIER_VERSION` bumped once from `1.0.1` to `1.0.2`, covering the combined change so a persisted `verification_json` outcome traces to the check revision that produced it (single bump; Task 2 does not bump again).
- Committed `tests/fixtures/verify/digit_location_extract.txt` (byte-identical to `base_extract.txt` except the location line is `Dublin 2`) plus the `with_digit_location` in-memory builder; both fixes proven end-to-end while the `novel_metric_extract.txt` (`Python 3.12`) negative control stays intact.
- The deliberate extraction-variation trade-off (a split org/title header reports `found=False` rather than mis-locating) is pinned by a test, so the limitation is visible rather than a silent coverage hole.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end — a digit-bearing entry location is grounded through check 4** - `01aae14` (fix)
2. **Task 2: Anchor each region on its own header; prove the committed location fixture end-to-end** - `426668c` (fix)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `app/verify/numbers.py` - `_allowed_for_entry` folds `entry.location` and its docstring names every source field; `_entry_lines` rewritten to anchor on the org-AND-title header line with an updated docstring.
- `app/verify/base.py` - `VERIFIER_VERSION` `"1.0.1"` -> `"1.0.2"`.
- `tests/fixtures/verify/digit_location_extract.txt` - committed extraction whose location line is `Dublin 2`.
- `tests/verify/fixtures.py` - new `with_digit_location(facts, *, location)` builder; added to `__all__`.
- `tests/verify/test_numbers.py` - `test_a_digit_bearing_location_is_not_a_surplus_candidate`, `test_a_bullet_naming_a_later_employer_does_not_bleed_into_its_region`, `test_the_committed_digit_location_extract_has_no_surplus_candidate`, `test_a_split_header_entry_is_reported_not_found_not_mislocated`.
- `tests/verify/test_text_checks.py` - `test_a_digit_bearing_location_still_passes_metric_containment`.

## Decisions Made
- **allowed-only grounding.** The location fold adds to `allowed` ONLY (never `excluded`), so the digit remains a region candidate and is excused by membership — the same asymmetry the 06-05 skill-label path relies on. This preserves the negative control: a fabricated digit in another region is still a candidate.
- **org-AND-title header anchor.** Requiring both needles matches the committed header line and cannot match a bullet merely naming the employer; it also removes the substring-vs-word fragility of short/common org names (`Meta` vs `metadata`). An org-only fallback was deliberately rejected as exactly the CR-02 defect.
- **Single version bump.** `VERIFIER_VERSION` is `1.0.2` for the combined CR-01 + CR-02 change; Task 2 changes `_entry_lines` under that same version and does not bump again.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Threat Flags

None — no new security-relevant surface. The changes narrow check 4's false-positive surface (T-06-34, T-06-35, T-06-36 mitigations implemented as planned) and `CheckResult.offending` still carries region ids and digit cores only; the extracted text remains a sha256 hash.

## Next Phase Readiness
- CR-01 and CR-02 are closed: a valid CV with a digit-bearing location, or with a bullet naming a later employer, verifies and its preview/download path is unblocked.
- `metric_containment` remains a hard fail and only `page_budget`/`layout_ats` warn; no check was weakened, deleted or downgraded.
- Full hermetic lane green: 1236 passed, 14 deselected, 2 xfailed (baseline 1231 + 5 new tests). Plan 06-09 remains as the last outstanding plan for Phase 06.

---
*Phase: 06-tailoring-verification*
*Completed: 2026-09-25*

## Self-Check: PASSED

- All 6 created/modified files exist on disk.
- Both task commits present: `01aae14`, `426668c`.
- Plan-level verification green: `tests/verify` 62 passed; `tests/verify tests/pipeline/test_tailor_stage.py` 71 passed; `tests/test_import_discipline.py` 9 passed; full lane 1236 passed, 14 deselected, 2 xfailed; `compileall -q app` clean.
