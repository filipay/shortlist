---
phase: 06-tailoring-verification
plan: 10
subsystem: testing
tags: [verification, check4, metric-containment, region-anchor, fail-closed, gap-closure]

# Dependency graph
requires:
  - phase: 06-tailoring-verification
    provides: "06-08's org+title lexical anchor and the Layer-2 check-4 call site inside compile_tailored; this plan replaces the anchor"
provides:
  - "structural date-range-adjacency region anchor in _entry_lines (a bullet cannot satisfy it)"
  - "fail-closed visible warn for an unanchorable check-4 region (never a silent candidates=[] pass)"
  - "committed org_title_collision_extract.txt literal-repro fixture carrying both finding strings"
  - "VERIFIER_VERSION 1.0.3 provenance bump (single bump for anchor + fail-closed)"
affects: [06-verification, verify-work, secure-phase]

# Actuals (#2632) — chars/4 over the realized diff, measured on the same scale as the plan estimate.
actuals:
  tokens: 5562
  tasks: 2
  commits: 2
plan_head_before: b531760392f0449ff89fb044be5c4c502e3d6725

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Structural region anchoring: a region start is gated by the entry's own date-range needle on the header line or its immediate successor"
    - "Fail-closed verification: a region the check cannot anchor surfaces as a visible warn naming the entry, never a silent skip"

key-files:
  created:
    - tests/fixtures/verify/org_title_collision_extract.txt
  modified:
    - app/verify/numbers.py
    - app/verify/text_checks.py
    - app/verify/base.py
    - tests/verify/test_numbers.py
    - tests/verify/test_text_checks.py

key-decisions:
  - "Replace, not tighten: the naked org+title substring anchor is DELETED and replaced by a date-range-adjacency discriminator a body bullet cannot satisfy"
  - "All three needles (org, title, dates) must be non-empty, so an empty needle cannot vacuously restore a content-only match"
  - "An unanchorable region is a visible warn naming the entry; fail precedence is preserved so an anchored surplus still hard-fails"
  - "Exactly one VERIFIER_VERSION bump (1.0.2 -> 1.0.3) covers both changes; no persisted-shape change (Alembic head stays 0004)"
  - "A region's END is unchanged: end = next found start, else end-of-text, so the last region keeps the trailing Skills block"

patterns-established:
  - "Region start = structural discriminator (dates adjacency), never a naked substring over lossy extracted text"
  - "An unscopeable region fails closed as a warn; a check never degrades to an empty candidate list and a silent pass"

requirements-completed: [TAIL-04]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "Structural date-range-adjacency region anchor: a bullet carrying a later entry's org AND title no longer hijacks its region (CR-01 / ESC-06-A)"
    requirement: TAIL-04
    verification:
      - kind: unit
        ref: "tests/verify/test_numbers.py#test_a_bullet_embedding_a_later_entrys_org_and_title_does_not_bleed_into_its_region"
        status: pass
      - kind: unit
        ref: "tests/verify/test_numbers.py#test_a_bullet_embedding_the_next_entrys_org_and_title_never_hijacks_a_region (6 parametrizations)"
        status: pass
      - kind: unit
        ref: "tests/verify/test_numbers.py#test_a_non_adjacent_date_range_is_not_a_region_start"
        status: pass
    human_judgment: false
  - id: D2
    description: "Fail-closed check 4: an unanchorable region surfaces as a visible warn naming the entry, never a silent pass (WR-01 / ESC-06-B)"
    requirement: TAIL-04
    verification:
      - kind: unit
        ref: "tests/verify/test_text_checks.py#test_an_unanchorable_region_is_a_visible_warn_not_a_silent_skip"
        status: pass
      - kind: unit
        ref: "tests/verify/test_text_checks.py#test_a_fabricated_digit_in_an_unanchorable_region_is_not_reported_pass"
        status: pass
      - kind: unit
        ref: "tests/verify/test_text_checks.py#test_an_unanchored_region_does_not_hide_an_anchored_surplus"
        status: pass
    human_judgment: false
  - id: D3
    description: "Committed literal-repro extraction carrying both finding repro strings; its two-entry plan yields metric_containment == pass"
    requirement: TAIL-04
    verification:
      - kind: unit
        ref: "tests/verify/test_numbers.py#test_a_bullet_embedding_a_later_entrys_org_and_title_does_not_bleed_into_its_region"
        status: pass
    human_judgment: false
  - id: D4
    description: "Closure authority (criterion E): an independent scoped /gsd-code-review 06 owns the closed verdict"
    requirement: TAIL-04
    verification: []
    human_judgment: true
    rationale: "The fix author does not certify closure. Criterion E mandates an independent reviewer; the orchestrator dispatches /gsd-code-review 06 and its verdict is not yet in."

# Metrics
duration: 10min
completed: 2026-09-25
status: complete
---

# Phase 06 Plan 10: CR-01 residual + WR-01 Summary

**Check 4 now anchors each region with a structural date-range-adjacency discriminator a body bullet cannot satisfy, and fails closed with a visible warn when it cannot anchor — closing the check-4 false positive and silent false negative.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-09-25T11:33:25Z
- **Completed:** 2026-09-25T11:43:25Z
- **Tasks:** 2
- **Files modified:** 6 (5 modified, 1 created)

## Accomplishments
- `_entry_lines` no longer matches naked org+title substrings: a region starts only when the line carries org AND title AND the entry's date-range needle is on that line or its immediate successor (all three needles non-empty). A bullet embedding a later entry's org+title can no longer start that region or donate its digits. The literal repro now yields `metric_containment == pass` (was `fail ['exp/acme-2019:5']`).
- A property test covers the whole lexical-collision class: 3 phrase templates x 2 three-entry corpora (distinct employers and one shared employer with distinct titles), asserting every region anchors at its own header and check 4 passes.
- `check_metric_containment` collects every `found=False` region into `unanchored` and returns a visible `warn` naming the entry — never the silent `continue`. Fail precedence is preserved: an anchored surplus digit still hard-fails.
- One `VERIFIER_VERSION` bump (1.0.2 -> 1.0.3) covers the combined anchor + fail-closed change; no schema/migration/dependency change.

## Task Commits

Each task was committed atomically:

1. **Task 1: structural date-adjacency region anchor** - `c841b52` (fix)
2. **Task 2: fail-closed on unanchorable check-4 regions** - `165d6c2` (fix)

**Plan metadata:** (pending) `docs(06-10): complete ...`

_Note: no TDD-mode tasks (TDD_MODE=false); each task is one commit._

## Files Created/Modified
- `app/verify/numbers.py` - `_entry_lines` region start gated on org AND title AND date-range adjacency; module + `_entry_lines` + `region_token_report` docstrings updated.
- `app/verify/text_checks.py` - `check_metric_containment` gains the `unanchored` collection and the `warn` return; module + function docstrings updated.
- `app/verify/base.py` - `VERIFIER_VERSION` `"1.0.2"` -> `"1.0.3"`.
- `tests/fixtures/verify/org_title_collision_extract.txt` - new committed two-entry extraction with both literal repro strings.
- `tests/verify/test_numbers.py` - 4 new tests (literal, last-region, non-adjacent-date, parametrized collision class).
- `tests/verify/test_text_checks.py` - 3 new fail-closed tests.

## Decisions Made
- **Replace, not tighten** (the round-2 root cause): the naked org+title substring anchor is deleted entirely; the date-range adjacency is the structural discriminator, chosen over the `---` separator because dates survive lossy pypdf extraction on the tokeniser's own premise.
- **Non-empty three-needle guard is load-bearing**: without it an empty needle would make the membership test vacuously true and silently restore a content-only match. An entry with empty org/title/dates is reported unanchorable (warn), not matched loosely.
- **Fail precedence**: `fail` (anchored surplus) is returned before the `warn` (unanchored region), so a warn can never mask a hard fail. `VerificationResult.passed` is unchanged (`no check has status fail`).
- **Single version bump**: 1.0.3 covers both changes because `verifier_version` is persisted into `cv_artifacts.verification_json`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed malformed `roadmap.update-plan-progress` output**
- **Found during:** close-out (roadmap update for phase 06)
- **Issue:** `gsd_run query roadmap.update-plan-progress "06"` rewrote Phase 6's plan line to `**Plans:** 10/10 plans executedned (7 executed; 3 gap-closure)` — a malformed token caused by the parenthetical note in the existing line.
- **Fix:** corrected to `**Plans:** 10/10 plans executed (7 executed; 3 gap-closure)`.
- **Files modified:** `.planning/ROADMAP.md`
- **Verification:** `grep -n "Plans:" .planning/ROADMAP.md` shows the corrected line (the other phases' `N/N plans complete` lines are untouched).
- **Committed in:** metadata commit.

No other deviations — the two production tasks executed exactly as written.

## Issues Encountered
None. Pre-fix failure-class evidence was captured first and matched the plan:
- Task 1 literal repro: pre-fix `check_metric_containment` = `fail ['exp/acme-2019:5']`, regions `[('exp/globex-2018', True, []), ('exp/acme-2019', True, ['5','5','7'])]`; the new literal/parametrized/non-adjacent tests failed pre-fix and pass post-fix.
- Task 2 first two fail-closed tests returned `pass` pre-fix and now return `warn`; the fail-precedence test passes both before and after (as intended).

## Verification Evidence

| Command | Result |
|---------|--------|
| `.venv/bin/python -m pytest -q tests/verify/test_numbers.py -x` | 35 passed |
| `.venv/bin/python -m pytest -q tests/verify/test_text_checks.py -x` | 14 passed |
| `.venv/bin/python -m pytest -q tests/verify -x` | 74 passed |
| `.venv/bin/python -m pytest -q tests/verify tests/pipeline/test_tailor_stage.py -x` | 84 passed |
| `.venv/bin/python -m pytest -q tests/test_import_discipline.py -x` | 9 passed |
| `.venv/bin/python -m pytest -q` | 1250 passed, 14 deselected, 2 xfailed (baseline 1238 + 12 new) |
| `.venv/bin/python -m compileall -q app` | clean |
| `grep -n "dates_needle" app/verify/numbers.py` | 4 matches |
| `grep -n "if org_needle and title_needle:" app/verify/numbers.py` | no match (bare guard removed) |
| `grep -n "unanchored" app/verify/text_checks.py` | 6 matches |
| `.venv/bin/python -c "from app.verify.base import VERIFIER_VERSION; assert VERIFIER_VERSION == '1.0.3'"` | exit 0 |

**Preserved controls:** `base_extract.txt` still found; last region still runs to end-of-text (trailing Skills block inside it); `novel_metric_extract.txt` still fails with `exp/northwind-labs-2021:3.12`; `page_budget`/`layout_ats` remain the only warn-only checks; Alembic head stays `0004`; no package installed.

## Criterion E — closure authority (PENDING independent review)

Criterion E is **not author-certified**. The scoped `/gsd-code-review 06` over the changed files (`app/verify/numbers.py`, `app/verify/text_checks.py`, `app/verify/base.py`, `tests/verify/test_numbers.py`, `tests/verify/test_text_checks.py`, `tests/fixtures/verify/org_title_collision_extract.txt`) is **PENDING independent scoped `/gsd-code-review 06`**; the orchestrator will dispatch it. The fix author does not claim closure; any new critical/warning finding on the changed files re-opens this fix.

## Known Stubs

None. No hardcoded empty values, placeholder text, or unwired data sources were introduced.

## Threat Flags

None. No new network endpoint, auth path, file-access pattern, or schema change at a trust boundary. The changes are confined to two pure verifier modules plus a version constant, a committed fixture and two test files; `offending` still carries entry ids and digit cores only.

## Next Phase Readiness
- The two failed Phase 6 check-4 truths (VERIFICATION truths 6 and 7; TAIL-04) are addressed at the code/test level; the phase verdict awaits criterion E's independent review and re-verification.
- No blockers introduced. `VERIFIER_VERSION` is provenance, not identity; previously persisted `verification_json` rows keep their written string.

---
*Phase: 06-tailoring-verification*
*Completed: 2026-09-25*

## Self-Check: PASSED

All 6 changed files and the SUMMARY exist on disk; both task commits (`c841b52`, `165d6c2`) exist in git history.
