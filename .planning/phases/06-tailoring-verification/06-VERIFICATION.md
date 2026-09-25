---
phase: 06-tailoring-verification
verified: 2026-09-25T14:05:00Z
status: gaps_found
score: 11/12 must-haves verified
covered_files:
  - .planning/REQUIREMENTS.md
  - .planning/phases/06-tailoring-verification/06-01-PLAN.md
  - .planning/phases/06-tailoring-verification/06-01-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-02-PLAN.md
  - .planning/phases/06-tailoring-verification/06-02-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-03-PLAN.md
  - .planning/phases/06-tailoring-verification/06-03-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-04-PLAN.md
  - .planning/phases/06-tailoring-verification/06-04-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-05-PLAN.md
  - .planning/phases/06-tailoring-verification/06-05-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-06-PLAN.md
  - .planning/phases/06-tailoring-verification/06-06-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-07-PLAN.md
  - .planning/phases/06-tailoring-verification/06-07-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-08-PLAN.md
  - .planning/phases/06-tailoring-verification/06-08-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-09-PLAN.md
  - .planning/phases/06-tailoring-verification/06-09-SUMMARY.md
  - .planning/phases/06-tailoring-verification/06-10-PLAN.md
  - .planning/phases/06-tailoring-verification/06-10-SUMMARY.md
  - app/verify/base.py
  - app/verify/numbers.py
  - app/verify/text_checks.py
  - tests/fixtures/verify/org_title_collision_extract.txt
  - tests/verify/test_numbers.py
  - tests/verify/test_text_checks.py
covered_digest: "v1:sha256:cd31bb22681de5dab3ede2e9d1827a2aa57af1b7edbf4f7bb5e75bd37b60c52c"
behavior_unverified: 1
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 9/12
  gaps_closed:
    - "Check 4 silently skips an unanchorable region (truth 7 / WR-01 / ESC-06-B): fixed — `check_metric_containment` now returns a visible `warn` naming the entry (independent repro reproduced)."
  gaps_remaining:
    - "Check 4 still false-fails a valid CV when an earlier bullet names a later entry's org AND title AND co-locates its date-range (truth 6 / WR-02 residual ESC-06-A class): independently reproduced `fail ['exp/acme-2019:5']`."
    - "Criterion E not satisfied: the scoped review returned unresolved Warning WR-02 on changed file `app/verify/numbers.py`."
  regressions: []
gaps:
  - truth: "Check 4 does not false-fail a valid CV when an earlier bullet names a later entry's org AND title (each region starts on its own header via a structural discriminator a body bullet cannot satisfy)."
    status: failed
    reason: >-
      The literal org+title-only repro is genuinely fixed (independent repro: `metric_containment == pass`).
      But the region anchor is still naked substring containment: `dates_adjacent` at `app/verify/numbers.py:169-171`
      uses `dates_needle in line` / `dates_needle in squashed_lines[index + 1]`, so a body bullet that co-locates
      the later entry's date-range satisfies the discriminator. Independently reproduced two ways on the current tree:
      (1) an earlier bullet containing the later org+title+date-range as prose, and (2) an extractor line-merge of an
      earlier bullet with the next header line followed by the dates line. Both return `fail ['exp/acme-2019:5']` on a
      correct CV. Because D-118's only recovery is a fresh tailor that re-runs the same predicate, preview/download are
      dead for that CV. This falsifies the 06-10 must-have claim of a discriminator "that a body bullet cannot satisfy"
      and the `_entry_lines` docstring absolute at `app/verify/numbers.py:129-131` ("a bullet never carries the entry's
      own date-range on itself or its successor"). Independently corroborated by `06-REVIEW.md` WR-02.
    artifacts:
      - path: "app/verify/numbers.py"
        issue: "`_entry_lines` anchor (lines 159-178); the dates needle is matched by naked substring containment (`:169-171`), not a structural boundary. Docstring false guarantee at `:129-131`."
      - path: "tests/verify/test_numbers.py"
        issue: "Property test (`:517-541`) mutates only the org+title dimension, never the dates needle, so the discriminator's true failure class is untested (documented as 'the whole lexical-collision class' at `:524`)."
    missing:
      - "Make the region start a boundary free text cannot accidentally satisfy — e.g. require the squashed candidate line to START with `org_needle` (the template emits org first; a bullet embeds it mid-line), or require the `---`/em-dash header separator, in addition to date adjacency; OR soften the docstring to state the residual explicitly and add a property case that mutates org+title+dates and pins the documented disposition (criterion E forbids closing with an unresolved warning)."
  - truth: "Closure authority (criterion E): the scoped review reports no unresolved critical/warning finding on the changed files before the phase is reported closed."
    status: failed
    reason: >-
      `06-10-PLAN.md:225` states: "Any new critical or warning finding on the changed files re-opens this fix; the
      phase is not reported closed until the scoped review reports no unresolved critical/warning finding on the
      changed files." `06-REVIEW.md` (status `issues_found`) returns Warning WR-02 on `app/verify/numbers.py`, a
      changed file. I re-examined WR-02 and reproduced it (see above): it is reachable, unguarded, and on a changed
      file. There is no evidence-based rebuttal. Criterion E therefore re-opens the fix.
    artifacts:
      - path: ".planning/phases/06-tailoring-verification/06-REVIEW.md"
        issue: "`status: issues_found`, `warning: 1` (WR-02) on a changed file; no resolved disposition."
    missing:
      - "Resolve WR-02 (structural anchor or documented + tested trade-off) and obtain a re-review with no unresolved critical/warning finding on the changed files."
deferred:
  - truth: "A failed CV cannot be ATTACHED to an application (the attach half of TAIL-05)."
    addressed_in: "Phase 7"
    evidence: "ROADMAP Phase 7 success criterion 3: 'every application links to the exact verified CV artefact that was sent'; the `ok`-only repository predicate is the cross-phase contract Phase 7's attach query consumes."
advisory: []
behavior_unverified_items:
  - truth: "A tailored RenderPlan compiles through the real pinned Tectonic engine and its extracted pypdf text passes the real Layer-2 checks."
    test: "In the container (`docker compose run --rm app pytest -m latex`, or generate + compile a scored listing), compile a tailored plan with the real engine and confirm a PDF plus a passing merged verification_json."
    expected: "A real PDF is produced and the merged VerificationResult passes (or reports only warn-tier checks)."
    why_human: >-
      Tectonic is absent from this dry host by design (D-69); the hermetic lane overrides the engine with a stub
      writing a canned PDF and monkeypatches `extract_pdf_text` to a committed fixture. Presence and wiring of the
      real path are verified by code reading (`app/pipeline/tailor.py`), but no test in this environment exercises the
      real engine/extraction behaviour on a tailored plan.
coincidental_reliance_items: []
---

# Phase 6: Tailoring + Verification — Verification Report

**Phase Goal:** A tailored, verified CV PDF the user can preview and download — shipped with its verification gate, never before it.
**Verified:** 2026-09-25T14:05:00Z
**Status:** gaps_found
**Re-verification:** Yes — after round-3 gap closure (06-10) fixing truths 6 and 7

**MVP-mode note:** ROADMAP.md marks Phase 6 `mode: mvp`, but the ROADMAP goal text is not in
user-story form. The plan `06-01-PLAN.md` `<objective>` supplies a valid MVP user story, used
here for User Flow Coverage:
*"As a job seeker working a ranked queue, I want to turn one listing into a CV tailored to it —
expressed as a typed patch over my real CV facts, verified, compiled and downloadable — so that
I can apply with a CV shaped to that job without ever risking a claim I cannot stand behind."*

## Scope of this re-verification

06-10 changed exactly six files (`app/verify/numbers.py`, `app/verify/text_checks.py`,
`app/verify/base.py`, `tests/verify/test_numbers.py`, `tests/verify/test_text_checks.py`,
`tests/fixtures/verify/org_title_collision_extract.txt`). Per re-verification rules the two
prior FAILED truths (6, 7) receive full 3-level verification; the ten prior PASSED truths
receive quick regression (existence + sanity) and the full hermetic suite is green.

## User Flow Coverage

| Step | Expected | Evidence in codebase | Status |
| ---- | -------- | -------------------- | ------ |
| Outcome clause: apply without risking an unsupported claim | Gate blocks fabrication; valid CVs verify | canary `tests/verify/test_no_free_text_path.py`, ok-only access control, `check_metric_containment` — **but check 4 still false-fails a valid CV for a bullet co-locating the next entry's date-range** | ✗ FAILED |

The other five user-flow steps (open page, generate, review, compile, download) were verified in
the prior report and are unaffected by 06-10; the full suite is green.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Generate produces exactly one typed patch from exactly one structured call, one audit row, no artifact/`.tex`/PDF. | ✓ VERIFIED (regression) | `app/pipeline/tailor.py:217-256`; `tests/pipeline/test_tailor_stage.py` green; file unchanged by 06-10 |
| 2 | Apply-tailoring is a typed patch over enumerated IDs, all-or-nothing, no free-text on the PDF path, bullet text byte-immutable. | ✓ VERIFIED (regression) | `app/domain/cv.py`; `tests/domain/test_patch_ops.py`, canary green |
| 3 | The user can preview the tailored CV and its change log before compiling. | ✓ VERIFIED (regression) | `_tailoring_review.html`; `tests/api/test_tailoring_review.py` green |
| 4 | The verification gate implements the ten advertised checks with the correct severities (`metric_containment` hard-fail; checks 8/9 warn-only). | ✓ VERIFIED (regression) | `app/verify/text_checks.py:104-116` fail precedence preserved; `page_budget`/`layout_ats` remain the only `_warn`; suite green |
| 5 | Digit-bearing entry locations (`Dublin 2`, Eircode, `Remote (GMT+1)`) do not false-fail check 4. | ✓ VERIFIED (regression) | `app/verify/numbers.py:181-199` location folds into `allowed`; `test_a_digit_bearing_location_is_not_a_surplus_candidate` green |
| 6 | **Check 4 does not false-fail a valid CV when an earlier bullet names a later entry's org AND title.** | ✗ FAILED | Literal org+title-only repro now passes, but WR-02 residual false-fails: independent repro returns `fail ['exp/acme-2019:5']` for a bullet co-locating the date-range (2 variants). See Gaps; `06-REVIEW.md` WR-02; `app/verify/numbers.py:169-171` |
| 7 | **Check 4 does not silently skip an unanchorable region (no fabricated-digit false negative).** | ✓ VERIFIED | `app/verify/text_checks.py:95-115` collects `unanchored` and returns `_warn` naming the entry with `fail` precedence; independent repro (empty title + fabricated `99`) returns `warn offending=['exp/acme-2019']`; 3 new tests green |
| 8 | A CV that fails verification is blocked (not downloadable), and no code path auto-repairs it. | ✓ VERIFIED (regression) | `app/pipeline/tailor.py` ("deliberately no repair path"); `cv_artifact_repo.py` ok-only SQL; `tests/verify/test_block_no_repair.py` green |
| 9 | The verified CV PDF can be previewed inline and downloaded (`?download=1`); no path is built from request text. | ✓ VERIFIED (regression) | `app/api/tailoring.py:501-530`; `tests/api/test_cv_pdf_route.py` green |
| 10 | WR-02: the four bullet ops ground ids against the bullet-id set and `ReorderSection.section_id` against the section-id set, so a non-family id raises `UnknownIdError`. | ✓ VERIFIED (regression) | `app/domain/cv.py`; `tests/domain/test_patch_ops.py` green |
| 11 | WR-01b: compile route honours `tailoring_enabled=False` with `409 tailoring_disabled` before `load_facts`. | ✓ VERIFIED (regression) | `app/api/tailoring.py`; `tests/api/test_tailoring_review.py` green |
| 12 | 06-09 WR-01: a raised `complete_structured` transport error writes exactly one `purpose="tailor"`, `status="error"` row, releases the in-flight slot, surfaces as typed 502. | ✓ VERIFIED (regression) | `app/pipeline/tailor.py:241-256`, `app/api/tailoring.py:387-392`; tests green |
| 13 | A tailored `RenderPlan` compiles through the real pinned Tectonic engine and its extracted pypdf text passes the real Layer-2 checks. | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Real path present and wired; no test exercises the real engine/extraction (Tectonic absent by design D-69) — see `behavior_unverified_items` |

**Score:** 11/12 truths verified (1 failed: truth 6 / WR-02; 1 present, behavior-unverified: real engine/extraction).
The prior report recorded 9/12; recomputing from the prior table (10 ✓, 2 ✗, 1 ⚠️) gives 10/12, so the prior headline
appears to have under-counted by one. This report counts statuses directly.

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | A failed CV cannot be ATTACHED to an application (attach half of TAIL-05) | Phase 7 | ROADMAP Phase 7 SC3: "every application links to the exact verified CV artefact that was sent" |

### Advisory (New Scope, Unevidenced)

None — the only new-scope concern (WR-02) is on a changed file and is therefore in scope and
blocking under criterion E, not advisory.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/verify/numbers.py` | Structural date-adjacency region anchor; docstrings match code | ⚠️ WIRED, NOT STRUCTURAL | Anchor at `:159-178` adds a non-empty three-needle guard and date adjacency; but the dates test is substring containment (`:169-171`) — a bullet co-locating the date-range still satisfies it. Docstring `:129-131` asserts a guarantee the code does not deliver |
| `app/verify/text_checks.py` | Fail-closed visible `warn` for an unanchorable region; `fail` precedence | ✓ VERIFIED | `:95-115`: `unanchored` collected, `_warn` naming the entry, `fail` returned first |
| `app/verify/base.py` | `VERIFIER_VERSION` `"1.0.3"` (single bump) | ✓ VERIFIED | `:22` `= "1.0.3"`; no `1.0.2` remains |
| `tests/fixtures/verify/org_title_collision_extract.txt` | Both literal repro strings | ✓ VERIFIED | `:7-8` carry both strings byte-for-byte (`grep -c` = 1 each) |
| `tests/verify/test_numbers.py` | Literal, last-region, non-adjacent-date, parametrized collision-class tests | ⚠️ PARTIAL | 4 new tests at `:371, :429, :439, :521`; the property test (`:517-541`) mutates only org+title, never dates |
| `tests/verify/test_text_checks.py` | Fail-closed warn tests | ✓ VERIFIED | `:197, :224, :264` green |
| Migration | none | ✓ VERIFIED | Alembic head `0004` (06-10 touched no schema) |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `_entry_lines` region start | `region_token_report` boundaries | date-adjacency predicate | ⚠️ PARTIAL | `app/verify/numbers.py:159-178` — gate is lexical substring (`:169-171`), so a date-carrying bullet hijacks (truth 6) |
| `region_token_report` `found=False` | `check_metric_containment` `unanchored` | explicit collection + `_warn` | WIRED | `app/verify/text_checks.py:95-115` — fixed (truth 7) |
| `VERIFIER_VERSION` | `VerificationResult.verifier_version` → persisted `verification_json` | `base.py:22`, `base.py:50` | WIRED | 1.0.3, single bump |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| check-4 region report | `RegionReport.candidates` / `.allowed` | `region_token_report(plan, extracted_text)` | Yes — real extraction text (fixture in hermetic lane) | ✓ FLOWING (predicate defective, truth 6) |
| `check_metric_containment` outcome | `CheckResult.status` / `.offending` | region reports + allowed sets | Yes | ✓ FLOWING (warn path now real) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| `tests/verify` lane | `.venv/bin/python -m pytest -q tests/verify` | `74 passed in 7.50s` | ✓ PASS |
| Full hermetic suite | `.venv/bin/python -m pytest -q` | `1250 passed, 14 deselected, 2 xfailed in 255.78s` | ✓ PASS |
| Truth 6 literal (org+title, no dates) | independent repro (`region_token_report` + `check_metric_containment`) | `pass`, regions found=True; candidates `['7']` for B | ✓ PASS |
| Truth 7 unanchorable + fabricated `99` | independent repro (empty title) | `warn offending=['exp/acme-2019']` | ✓ PASS |
| **WR-02 variant 1** (bullet carries org+title+date-range prose) | independent repro | B region candidates `['5','7']` → `fail ['exp/acme-2019:5']` | ✗ FAIL |
| **WR-02 variant 2** (extractor line-merge of bullet with next header; dates successor) | independent repro | B region candidates `['5','7']` → `fail ['exp/acme-2019:5']` | ✗ FAIL |
| Negative control | `test_a_novel_metric_token_fails_metric_containment` | fail `['exp/northwind-labs-2021:3.12']` | ✓ PASS |
| Real-engine latex lane | `.venv/bin/python -m pytest -m latex` | cannot run on host — Tectonic absent (D-69) | ? SKIP |

Repro commands (constructed two-entry `RenderPlan`, text lines `header / dates / bullet / next header`):

```
variant 1 bullet: "Partnered with Acme Senior Engineer 2019-01 -- 2019-12 to cut 5 incidents"
variant 2 lines : "Liaised with the Globex Inc Manager on 5 projects Acme Senior Engineer"
                  "2019-01 -- 2019-12"
both -> region exp/acme-2019 candidates=['5','7'] -> metric_containment: fail ['exp/acme-2019:5']
```

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes and no PLAN-declared probes exist for this phase. Step 7c: NOT APPLICABLE.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| TAIL-01 | 06-01, 06-07, 06-09 | Generate a CV tailored to a specific listing | ✓ SATISFIED | one call → one patch; generate route; off-switch guard; typed 502 |
| TAIL-02 | 06-01, 06-09 | Typed patch over enumerated IDs, no free-text on the PDF path | ✓ SATISFIED | schema + canary + raised-error audit row |
| TAIL-03 | 06-01 | Never rewrites/invents claims; bullet text immutable | ✓ SATISFIED | carried-through `Bullet` objects; test |
| TAIL-04 | 06-02, 06-05, 06-08, 06-10 | Verification gate checks the compiled PDF for unsupported content | ✗ BLOCKED | truth 7 fixed; truth 6 still false-fails under WR-02; criterion E re-opened (`nyquist_compliant: false`) |
| TAIL-05 | 06-04 | Failed CV blocked; cannot be downloaded or attached | ✓ SATISFIED (download) / DEFERRED (attach → Phase 7) | ok-only SQL + route; attach is Phase 7 |
| TAIL-06 | 06-02, 06-03 | Verification never auto-repairs — it blocks | ✓ SATISFIED | no repair branch; tests |
| TAIL-07 | 06-03 | Review the tailored CV and change log before compiling | ✓ SATISFIED | review route/template; guard; tests |
| TAIL-08 | 06-03, 06-06 | Anything dropped is listed explicitly with a reason | ✓ SATISFIED | `dropped_bullets` struck + reason; phantom-change path closed |
| UI-05 | 06-04, 06-07 | Preview and download the tailored CV PDF | ✓ SATISFIED | inline + `?download=1`; tests |

All 9 phase requirement IDs appear in at least one plan's `requirements:` field. No ORPHANED requirements.
`REQUIREMENTS.md:73` currently checks `TAIL-04` as `[x]` and lists it `Complete` (`:219`) — that traceability
status is **stale**: this re-verification finds TAIL-04 still BLOCKED.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `app/verify/numbers.py` | 169-171 | Date-range needle matched by naked substring containment — not a discriminator free text cannot accidentally satisfy (AGENTS.md convention 1) | ⚠️ Warning (criterion E re-open) | A date-carrying bullet hijacks the later region → false-fail (truth 6) |
| `app/verify/numbers.py` | 129-131 | Docstring absolute false guarantee ("a bullet never carries the entry's own date-range on itself or its successor") — AGENTS.md convention 6 | ⚠️ Warning | Suppresses scrutiny; code does not deliver it (WR-02) |
| `tests/verify/test_numbers.py` | 524 | Property test claims "the whole lexical-collision class" but never mutates the dates dimension — AGENTS.md convention 4 | ⚠️ Warning | The chosen discriminator's boundary is untested |
| `app/verify/numbers.py` | 273 | Dead `_region_structured_cores(plan, "")` operand (always `set()`), reads as scoping structured content to a nonexistent region | ℹ️ Info | Misleading; no behavioural effect (IN-01) |
| `tests/verify/test_numbers.py` | 530-532 | Substring membership assertion `str(earlier[2]) not in report.candidates` over a list | ℹ️ Info | Minor false-pass potential; surrounding `status == "pass"` carries the signal (IN-02) |

No `TBD`/`FIXME`/`XXX` debt markers were found in the phase's modified files. **No blocking check was
weakened** — `metric_containment` still returns `_fail` on an anchored surplus; `page_budget`/`layout_ats`
remain the only `_warn` checks; a warn never blocks. **No new dependency added.** **Alembic head is still `0004`.**

### Human Verification Required

1. **Real-engine tailored compile** — In the container (`docker compose run --rm app pytest -m latex`, or
   generate + compile a scored listing), compile a tailored plan with the real pinned Tectonic engine;
   confirm a real PDF and the persisted merged `verification_json`. The hermetic lane stubs engine and
   extraction (D-69).
2. **Fail-vs-warn legibility and block-as-outcome** — Open the tailoring review and the blocked state;
   confirm a failing check is visually distinct from a warning and that the block reads as a reviewable
   outcome with a clear recovery.

### Gaps Summary

Round-3 gap closure (06-10) is **half real**: truth 7 is genuinely closed, truth 6 is not, and criterion E
re-opens the fix.

**Truth 7 — CLOSED (VERIFIED).** `check_metric_containment` (`app/verify/text_checks.py:95-115`) now collects
every `found=False` region into `unanchored` and returns a visible `warn` naming the entry, with `fail`
precedence preserved. My independent repro (empty title, fabricated `99`) returns
`warn offending=['exp/acme-2019']` — the fabricated digit is no longer invisible. Passed remains `True`, so a
valid CV still downloads.

**Truth 6 — FAILED (WR-02).** The literal org+title-only repro is fixed (independent repro `pass`). But the
region anchor remains naked substring containment: `dates_adjacent` (`app/verify/numbers.py:169-171`) is
`dates_needle in line or (... in squashed_lines[index + 1])`. A body bullet that co-locates the later entry's
date-range satisfies all three needles and still hijacks the region. I reproduced this two ways on HEAD:
(1) a bullet carrying the later org+title+date-range as prose; (2) an extractor line-merge of an earlier bullet
with the next header line, dates on the successor — no adversarial date prose needed. Both return
`fail ['exp/acme-2019:5']` on a correct CV. This falsifies the must-have claim of a discriminator "that a body
bullet cannot satisfy" and the docstring absolute at `:129-131`. `06-REVIEW.md` independently raises it as WR-02.

**Criterion E — NOT SATISFIED.** `06-10-PLAN.md:225` binds: no new critical/warning on the changed files may
remain. `06-REVIEW.md` (`status: issues_found`, `warning: 1`) returns WR-02 on changed file `app/verify/numbers.py`.
WR-02 is reachable, unguarded, and on a changed file; I found no evidence-based rebuttal. The fix is therefore
re-opened and the phase is not closed.

Because a must-have truth is FAILED and criterion E is unmet, the phase goal ("a tailored, verified CV PDF the
user can preview and download") is not achieved for the affected CV shapes. A fix direction is available and
was checked by the reviewer: require the squashed candidate line to **start** with `org_needle` (the template
emits org first; a bullet embeds it mid-line) and/or require the `---` header separator, in addition to date
adjacency — or explicitly document and test the residual trade-off. `REQUIREMENTS.md`'s `TAIL-04` "Complete"
mark should be reverted to open.

---

_Verified: 2026-09-25T14:05:00Z_
_Verifier: the agent (gsd-verifier)_
