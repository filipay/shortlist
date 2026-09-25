---
phase: 06-tailoring-verification
plan: 11
subsystem: testing
tags: [verification, check4, metric-containment, region-anchor, leak-guard, gap-closure]

# Dependency graph
requires:
  - phase: 06-tailoring-verification
    provides: "06-10's org+title+date-adjacency lexical anchor, its fail-closed unanchored warn, and the Layer-2 check-4 call site inside compile_tailored; this plan tightens the anchor and adds the region-end bound"
provides:
  - "org-first structural region start in _entry_lines (line.startswith(squash(org)), cv.tex.jinja:58 emits org first)"
  - "region-end leak guard in region_token_report: an anchored region is bounded at the first line whose squash contains a later unanchored entry's org, title or date-range, excluding the anchored entry's own date line by position and its own location/bullet lines by squash equality"
  - "four committed literal-repro fixtures (variant-1, variant-2 merge, digit-bearing header, identical dates)"
  - "literal, leak-guard (parametrized) and property (org+title+dates) regression tests, plus the IN-02 exact-membership fix"
  - "explicit residual statements replacing the falsified absolute docstring guarantees"
  - "VERIFIER_VERSION 1.0.4 provenance bump (single bump for the anchor + end-bound)"
affects: [06-verification, verify-work, secure-phase]

# Actuals (#2632) — chars/4 over the realized diff, measured on the same scale as the plan estimate.
actuals:
  tokens: 7526
  tasks: 3
  commits: 2
plan_head_before: 9755154693affdbade8ab3a3243c6e426eab13ba

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Org-first structural region anchoring: a region start is gated by the line BEGINNING with squash(org), so a mid-line mention in a body bullet cannot hijack it"
    - "Region-end leak guard: an anchored region's end is bounded at a later unanchored entry's org/title/date-range occurrence, with the anchored entry's own content excluded (date line by position, location/bullet lines by squash equality)"
    - "Stated residual: line-granularity limits are documented positively; no absolute negative guarantee survives in the region-segmentation prose"

key-files:
  created:
    - tests/fixtures/verify/org_title_dates_collision_extract.txt
    - tests/fixtures/verify/org_title_dates_merge_extract.txt
    - tests/fixtures/verify/digit_bearing_header_extract.txt
    - tests/fixtures/verify/identical_dates_extract.txt
  modified:
    - app/verify/numbers.py
    - app/verify/base.py
    - tests/verify/test_numbers.py

key-decisions:
  - "Org-first, not content-only: _entry_lines accepts a header only when the squashed line starts with org_needle in addition to title presence and date adjacency; a body line that embeds a later org mid-line no longer starts that region (WR-02 / ESC-06-A residual)"
  - "The org-first anchor alone converts variant 2 into a different false fail, so a region-end bound is required: an anchored region is bounded at the first line whose squash CONTAINS a later unanchored entry's org, title or date-range"
  - "The bound excludes the anchored entry's OWN date line BY POSITION (the header or its immediate successor that carries its date-range), not by global squash equality, because two entries may share an identical date-range; its own location/bullet lines are excluded by squash equality"
  - "The bound uses containment, not equality, so a merged header/date line and a digit-bearing header line before its dates both bound (round-3 shapes)"
  - "Both falsified absolute docstring guarantees are removed and the line-granularity residual is stated explicitly; the ast docstring scan over the never/cannot/impossible family near 'bullet' is clean"
  - "The always-empty structured-cores operand in the unanchored branch is removed (IN-01); the property-loop candidate assertion uses exact set membership (IN-02)"
  - "Exactly one VERIFIER_VERSION bump (1.0.3 -> 1.0.4) covers the anchor + end-bound change; no persisted-shape change (Alembic head stays 0004)"

patterns-established:
  - "Region start = structural org-first boundary over lossy extracted text, never naked substring containment"
  - "An unanchored neighbour is a visible warn, never a silent pass and never a mis-charge to the preceding region"
  - "A fix author documents review-readiness and delegates the closed verdict to an independent scoped review"

requirements-completed: [TAIL-04]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "Org-first region anchor: an earlier bullet co-locating a later entry's org, title AND date-range no longer hijacks its region (variant-1 literal repro)"
    requirement: TAIL-04
    verification:
      - kind: unit
        ref: "tests/verify/test_numbers.py#test_a_bullet_carrying_the_next_entrys_org_title_and_dates_does_not_bleed_into_its_region"
        status: pass
      - kind: unit
        ref: "tests/verify/test_numbers.py#test_a_bullet_embedding_the_next_entrys_org_title_and_dates_never_hijacks_a_region (6 parametrizations)"
        status: pass
      - kind: unit
        ref: "tests/verify/test_numbers.py#test_a_non_adjacent_date_range_is_not_a_region_start"
        status: pass
    human_judgment: false
  - id: D2
    description: "Region-end leak guard: an unanchored later entry's digits are not charged to the preceding region for the merged, digit-bearing-header and identical-date shapes; the unanchored entry surfaces as a visible warn"
    requirement: TAIL-04
    verification:
      - kind: unit
        ref: "tests/verify/test_numbers.py#test_an_unanchored_entry_does_not_donate_its_digits_to_the_previous_region"
        status: pass
      - kind: unit
        ref: "tests/verify/test_numbers.py#test_an_unanchored_entrys_date_cores_are_never_absorbed_by_the_previous_region (3 parametrizations)"
        status: pass
      - kind: unit
        ref: "tests/verify/test_numbers.py#test_a_digit_bearing_or_identical_date_neighbour_is_not_charged_to_the_preceding_region (2 parametrizations)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Own-content guard: the end bound does not collapse or truncate an anchored region at its own date/bullet line, so a fabricated digit in the anchored region's own content still hard-fails"
    requirement: TAIL-04
    verification:
      - kind: unit
        ref: "tests/verify/test_numbers.py#test_the_region_end_bound_never_shortens_an_anchored_region_at_its_own_content (2 parametrizations)"
        status: pass
      - kind: unit
        ref: "tests/verify/test_text_checks.py#test_a_novel_metric_token_fails_metric_containment (negative control)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Single VERIFIER_VERSION provenance bump to 1.0.4 with no earlier version string remaining; Alembic head stays 0004 and no package installed"
    requirement: TAIL-04
    verification:
      - kind: unit
        ref: "app/verify/base.py#VERIFIER_VERSION; grep -rn '1.0.3' app tests -> no match"
        status: pass
    human_judgment: false
  - id: D5
    description: "Closure authority (criterion E): an independent scoped /gsd-code-review 06 owns the closed verdict"
    requirement: TAIL-04
    verification: []
    human_judgment: true
    rationale: "The fix author does not certify closure. Criterion E mandates an independent reviewer; the orchestrator dispatches /gsd-code-review 06 over the changed files and its verdict is not yet in."

# Metrics
duration: 18min
completed: 2026-09-25
status: complete
---

# Phase 06 Plan 11: Check-4 org-first region anchor + region-end leak guard Summary

**Check 4's region start now requires the extracted line to BEGIN with the entry's org (the template emits org first), and an anchored region's end is bounded at a later unanchored entry's org/title/date-range, so both WR-02 reproductions stop false-failing while a fabricated digit in the anchored region still hard-fails.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-09-25T15:13:06Z
- **Completed:** 2026-09-25T15:31:41Z
- **Tasks:** 3
- **Files modified:** 7 (4 created, 3 modified)

## Accomplishments
- `_entry_lines` region start is now an org-first structural boundary: a line is accepted only when `squash(line).startswith(squash(org))` AND it carries `squash(title)` AND the entry's date-range needle is on that line or its immediate successor. The variant-1 literal (`Partnered with Acme Senior Engineer 2019-01 -- 2019-12 to cut 5 incidents`) no longer starts B's region; the pre-fix `fail ['exp/acme-2019:5']` is now `pass`.
- `region_token_report` bounds an anchored region's end at the FIRST line after its header whose squash CONTAINS any non-empty squash of a later unanchored entry's org, title OR date-range. The anchored entry's own date line is excluded BY POSITION and its own location/bullet lines by squash equality, and the region never shrinks below its header. The merged-with-dates, merged-with-dates-on-successor, digit-bearing-header-before-dates and shared-identical-date shapes all return a visible `warn` naming the unanchored entry instead of a false `fail` on the anchored one.
- The own-content guard is pinned: with an identical shared date-range or the anchored entry's own bullet quoting the later date-range, the bound does not collapse the region at that line, so a fabricated `99` in the anchored region's own content still yields `fail ['exp/acme-2018:99']` (the uncorrected containment rule returned `warn` with empty candidates — the false PASS this phase exists to prevent).
- Both falsified absolute docstring guarantees are removed and the line-granularity residual is stated explicitly and positively; the ast docstring scan over the never/cannot/impossible family near "bullet" is clean. The always-empty structured-cores operand (IN-01) is removed and the property-loop candidate assertion uses exact set membership (IN-02).
- One `VERIFIER_VERSION` bump (1.0.3 -> 1.0.4) covers the combined change; no schema/migration/dependency change (Alembic head stays `0004`).

## Task Commits

Each task was committed atomically:

1. **Task 1: Harden the region anchor to an org-first boundary and stop neighbour leak** - `7a168a9` (fix)
2. **Task 2: Commit the two literal reproductions and pin the failure class (dates dimension) plus the leak guard** - `6711384` (test)
3. **Task 3: Criterion E — make closure independently reviewable without claiming it** - no production change; evidence recorded in this SUMMARY (the plan's Task 3 is documentation/evidence only, committed with the plan metadata).

**Plan metadata:** `docs(06-11): complete check-4 org-first anchor + leak guard plan` (this SUMMARY, STATE.md, ROADMAP.md)

_Note: no TDD-mode tasks (TDD_MODE=false); each production task is one commit._

## Files Created/Modified
- `app/verify/numbers.py` - `_entry_lines` region start requires `line.startswith(org_needle)`; `region_token_report` computes squashed lines once, removes the dead structured-cores operand, and bounds an anchored region's end against later unanchored entries with positional own-date exclusion and own location/bullet squash-equality exclusion; module, `_entry_lines` and `region_token_report` docstrings state the org-first boundary, the region-end containment rule, the positional exclusion and the residual, with no absolute negative bullet claim.
- `app/verify/base.py` - `VERIFIER_VERSION` `"1.0.3"` -> `"1.0.4"` (the single bump).
- `tests/fixtures/verify/org_title_dates_collision_extract.txt` - new committed two-entry extraction carrying the variant-1 literal repro string.
- `tests/fixtures/verify/org_title_dates_merge_extract.txt` - new committed two-entry extraction carrying the variant-2 merged line and the dates on the successor.
- `tests/fixtures/verify/digit_bearing_header_extract.txt` - new committed extraction with `3M ---` / `Manager` before `2019-01 -- 2019-12`.
- `tests/fixtures/verify/identical_dates_extract.txt` - new committed extraction where both entries render `2019-01 -- 2019-12`.
- `tests/verify/test_numbers.py` - 6 new tests (15 parametrizations): the variant-1 literal, the variant-2 merge, the 3-shape unanchored leak guard, the 2-shape digit-bearing/identical-date neighbour, the 2-shape own-content collision, and the 6-case org+title+dates property test; the IN-02 exact-membership fix.

## Decisions Made
- **Org-first over content-only** (WR-02 root cause): the region start is the position the template emits the org (`cv.tex.jinja:58`), so a body line embedding the later org mid-line cannot satisfy it. Requiring title and date adjacency is retained.
- **A leak guard is required by the anchor change**: on an org-first-only tree, variant 2 becomes a different false fail (`fail ['exp/globex-2018:7']`) because the unanchored neighbour's digits fall inside the preceding anchored region. The bound restores a visible `warn`.
- **Containment, not equality**: the real template emits org/title/dates on one line, so an equality-only rule misses the merged shape; containment with the own-content exclusions preserves the controls.
- **Positional own-date exclusion, not global equality**: with a shared identical date-range, a global squash-equality exclusion suppressed the bound and let the anchored region collapse to its header — a false PASS. Excluding the own date line by position fixes that while still protecting the anchored entry.
- **Residuals stated, not hidden**: both falsified absolutes removed; the line-granularity residual (a later entry whose only org/title/date occurrence is on a line the own-content exclusion protects) is documented as a non-weakened, warn-surfacing residual.
- **Single version bump**: 1.0.4 covers the anchor + end-bound change because `verifier_version` is persisted into `cv_artifacts.verification_json`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Consistency] Converted four pre-existing substring-membership assertions to exact set membership**
- **Found during:** Task 2 (IN-02 fix)
- **Issue:** The Task 2 acceptance criterion requires `grep -n "not in report.candidates" tests/verify/test_numbers.py` to report no match, but four pre-existing tests (`test_a_date_core_is_never_a_candidate`, `test_a_page_number_line_is_never_a_candidate`, `test_a_digit_in_a_skill_label_appearing_in_the_region_is_not_a_candidate`) used `"<literal>" not in report.candidates`. Fixing only the property loop (as the action text described) would leave the criterion failing.
- **Fix:** changed those four assertions to `not in set(report.candidates)`, mirroring the IN-02 exact-membership form. This is semantics-preserving for the current fixtures and strictly more correct (a candidate `"20211"` can no longer mask `"2021"`), and does not weaken any check.
- **Files modified:** `tests/verify/test_numbers.py`
- **Verification:** `tests/verify/test_numbers.py` 50 passed, `tests/verify` 108 passed; acceptance grep now reports no `not in report.candidates`.
- **Committed in:** `6711384` (Task 2 commit)

No other deviations — the production tasks executed as written.

## Issues Encountered
- The harness blocked shell-level overwrite of a tracked source file when capturing pre-fix regression evidence (and blocked writing a throwaway script under `/tmp/opencode`). Worked around non-destructively: loaded the 06-10 `numbers.py` from `git show` output via `importlib` and injected it into `text_checks` before calling the unchanged check. No repository file was mutated for the reproduction.
- Pre-fix reproduction (06-10 tree, new tests kept) — scoped to the rule each test pins:
  - `variant_1_literal` -> `fail ['exp/acme-2019:5']` (matches the plan's demonstrated repro).
  - `merged_header_with_dates` -> `fail ['exp/acme-2019:5']` (variant-2 class).
  - `digit_bearing_header` -> `fail` including `exp/acme-2018:2019`, `exp/acme-2018:3`, `exp/acme-2018:7` (shape a / round-3).
  - `identical_dates` -> `fail ['exp/acme-2018:7']` (shape b / round-3).
  - `own_date_line_shared_range` -> `fail ['exp/acme-2018:99']` on pre-fix 06-10 (no region-end bound), so that test PASSES pre-fix by design; it exists to fail against the UNCORRECTED containment rule (which returned `warn ['exp/globex-2019']` with empty candidates).

## Verification Evidence

| Command | Result |
|---------|--------|
| `.venv/bin/python -m pytest -q tests/verify/test_numbers.py -x` | 50 passed |
| `.venv/bin/python -m pytest -q tests/verify/test_numbers.py tests/verify/test_text_checks.py -x` | 64 passed |
| `.venv/bin/python -m pytest -q tests/verify tests/pipeline/test_tailor_stage.py tests/test_import_discipline.py -x` | 108 passed |
| `.venv/bin/python -m pytest -q` | 1265 passed, 14 deselected, 2 xfailed (baseline 1250 + 15 new) |
| `.venv/bin/python -m compileall -q app` | clean |
| `grep -n "startswith(org_needle)" app/verify/numbers.py` | 1 match |
| `grep -n "never carries" / "can no longer start that employer" / "can never satisfy" app/verify/numbers.py` | no match (both falsified absolutes removed) |
| ast docstring scan over `bullet[^.]{0,140}(never\|cannot\|impossible)` | clean |
| `grep -n '_region_structured_cores(plan, "")' app/verify/numbers.py` | no match (IN-01) |
| `grep -n "not in report.candidates" tests/verify/test_numbers.py` | no match; `not in set(report.candidates)` = 6 matches (IN-02 + consistency) |
| `grep -rn "1\.0\.3" app tests` | no match; `VERIFIER_VERSION == "1.0.4"` |
| `git ls-files -- <seven declared paths>` | exactly 7 |
| Alembic versions | highest `0004_ranking_config.py`; no `pyproject.toml`/lock diff (no package installed) |

**Invariant checks (Task 3):** (a) changed set is exactly the seven declared paths; (b) ast docstring scan clean; (c) `VERIFIER_VERSION` 1.0.4, no `1.0.3` in `app/` or `tests/`; (d) `novel_metric_extract.txt` still `fail ['exp/northwind-labs-2021:3.12']`; (e) only `page_budget` and `layout_ats` cannot fail (warn-only) — `metric_containment` still hard-fails an anchored surplus and `passed` remains `no check has status fail`; (f) Alembic head `0004`, no package installed; (g) round-3 (a)/(b) shapes return `warn` with the anchored entry not named, and the own-content shapes still return `fail ['exp/acme-2018:99']`.

**Preserved controls:** `base_extract.txt` still anchors and the last region still runs to end-of-text (trailing Skills block inside it); split-header and non-adjacent-date cases are still `found=False`; `missing_entity_extract.txt` still `found=False`; `digit_location_extract.txt`/`digit_skill_extract.txt` still pass; `verify_text.passed` is still `all(check.status != 'fail')`.

## Criterion E — closure authority

Criterion E is **not author-certified**. The fix author does not certify closure, and this SUMMARY does not claim the phase is closed or that WR-02 is resolved.

WR-02's demonstrated reproductions (variant 1 and variant 2) now pass or warn without a false fail, and the round-3/own-content shapes are pinned by committed tests. Closure is owned by the independent scoped `/gsd-code-review 06` over the changed files (`app/verify/numbers.py`, `app/verify/base.py`, `tests/verify/test_numbers.py`, `tests/fixtures/verify/org_title_dates_collision_extract.txt`, `tests/fixtures/verify/org_title_dates_merge_extract.txt`, `tests/fixtures/verify/digit_bearing_header_extract.txt`, `tests/fixtures/verify/identical_dates_extract.txt`), which the orchestrator dispatches after this plan executes. Any new critical or warning finding on the changed files re-opens the fix; WR-02 re-opens if the review returns it unresolved.

## Known Stubs

None. No hardcoded empty values, placeholder text, or unwired data sources were introduced. The region-end bound and the org-first anchor are fully wired into the check-4 path.

## Threat Flags

None. No new network endpoint, auth path, file-access pattern, or schema change at a trust boundary. The changes are confined to one pure verifier module, one version constant, four committed fixtures and one test file; `offending` still carries entry ids and digit cores only and `VerificationResult` keeps `extra="forbid"`.

## Next Phase Readiness
- The still-FAILED truth 6 of `06-VERIFICATION.md` (check 4 false-fails a valid CV) is addressed at the code/test level and criterion E is made review-ready; the phase verdict awaits the independent scoped re-review.
- No blockers introduced. `VERIFIER_VERSION` is provenance, not identity; previously persisted `verification_json` rows keep their written string. Alembic head stays `0004`; no dependency added.

---
*Phase: 06-tailoring-verification*
*Completed: 2026-09-25*

## Self-Check: PASSED

- All 7 changed files exist on disk (2 modules, 4 fixtures, 1 test file) plus this SUMMARY.
- Both task commits exist in git history: `7a168a9` (Task 1) and `6711384` (Task 2).
- `.venv/bin/python -m pytest -q` -> 1265 passed, 14 deselected, 2 xfailed; `.venv/bin/python -m compileall -q app` clean.
