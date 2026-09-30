---
phase: 06-tailoring-verification
verified: 2026-09-30T12:02:22Z
status: human_needed
score: 17/18 must-haves verified
covered_files:
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
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
  - .planning/phases/06-tailoring-verification/06-11-PLAN.md
  - .planning/phases/06-tailoring-verification/06-11-SUMMARY.md
  - app/api/tailoring.py
  - app/db/repositories/cv_artifact_repo.py
  - app/domain/cv.py
  - app/pipeline/tailor.py
  - app/verify/base.py
  - app/verify/numbers.py
  - app/verify/text_checks.py
  - tests/fixtures/verify/digit_bearing_header_extract.txt
  - tests/fixtures/verify/identical_dates_extract.txt
  - tests/fixtures/verify/org_title_collision_extract.txt
  - tests/fixtures/verify/org_title_dates_collision_extract.txt
  - tests/fixtures/verify/org_title_dates_merge_extract.txt
  - tests/fixtures/verify/org_first_bullet_extract.txt
  - tests/fixtures/verify/org_first_merge_extract.txt
  - tests/verify/test_numbers.py
  - tests/verify/test_text_checks.py
covered_digest: "v1:sha256:3002049e07285b5d9009382eb75ee3ccdbf1cb7fdfbaf8953ebeb5e4b9a1d9c0"
behavior_unverified: 1
overrides_applied: 0
requirements_verified:
  - TAIL-01
  - TAIL-02
  - TAIL-03
  - TAIL-04
  - TAIL-05
  - TAIL-06
  - TAIL-07
  - TAIL-08
  - UI-05
re_verification:
  previous_status: gaps_found
  previous_score: 15/18
  gaps_closed:
    - "Truth 6 (check 4 false-failed a valid CV when an earlier entry's bullet named a later entry's org AND title): CLOSED. `da06178` adds a `_dash_fold` helper and a separator conjunct to `_entry_lines` (a region start now also requires the template's org/title dash separator, numbers.py:219). Both original repro shapes reproduced independently at HEAD: shape 1 -> `pass`, shape 2 -> `warn ['exp/acme-2019']`. The negative control still hard-fails (`fail ['exp/globex-2018:99']`)."
    - "Truth 15 (`numbers.py` docstring claimed the residual degraded to a `warn` when it returned `fail`): CLOSED. The rewritten residual (numbers.py:169-183) states the full-header reproduction is a hard `fail` (structurally irreducible), that a real header losing its separator degrades to a visible `warn`, and that it is not a global no-false-fail guarantee. Independently reproduced both dispositions; no false-guarantee phrase remains."
    - "Criterion E re-satisfied: `06-REVIEW.md` is `clean` (0 critical, 0 warning, 5 info, all resolved) at `3b3842b`; the changed set is exactly the 5 declared paths."
  gaps_remaining: []
  regressions: []
truths:
  - id: 1
    truth: "Generate produces exactly one typed patch from exactly one structured call, one audit row, and no artifact/.tex/PDF."
    status: pass
    evidence: "app/pipeline/tailor.py:217-256; tests/pipeline/test_tailor_stage.py green (full suite)."
  - id: 2
    truth: "Apply-tailoring is a typed patch over enumerated IDs, all-or-nothing, no free-text field on the PDF path, bullet text byte-immutable."
    status: pass
    evidence: "app/domain/cv.py:401-441 (typed Literal ops); apply_patch carries Bullet objects (app/domain/cv.py:578,691-713,758-786); tests/verify/test_no_free_text_path.py + tests/domain/test_patch_ops.py green."
  - id: 3
    truth: "User can preview the tailored CV and its change log before compiling; dropped items are listed with a reason."
    status: pass
    evidence: "app/web/templates/html/_tailoring_review.html; app/api/tailoring.py review route; tests/api/test_tailoring_review.py green."
  - id: 4
    truth: "The verification gate implements its checks with the correct severities (metric_containment can hard-fail; page_budget/layout_ats warn-only)."
    status: pass
    evidence: "app/verify/text_checks.py:104-116, :134-143, :146-169; tests/verify/test_text_checks.py green; full suite 1533 passed."
  - id: 5
    truth: "Digit-bearing entry locations (Dublin 2, Eircode, Remote (GMT+1)) do not false-fail check 4."
    status: pass
    evidence: "app/verify/numbers.py:199-200 folds location into allowed; test_a_digit_bearing_location_is_not_a_surplus_candidate green."
  - id: 6
    truth: "Check 4 does not false-fail a valid CV when an earlier entry's bullet names a later entry's org AND title (including the org-FIRST prefix-collision and extractor-merge shapes)."
    status: pass
    evidence: >-
      Separator conjunct at app/verify/numbers.py:219 (`dash_lines[index].startswith(org_dash + '-')`)
      with `_dash_fold` at :69-82. Independent repro: shape 1 (bullet `Acme Senior Engineer 2019-01 --
      2019-12 cut 5 incidents`) -> `pass`; shape 2 (merge `Acme Senior Engineer contract -- delivered 5
      projects Acme --- Senior Engineer`) -> `warn ['exp/acme-2019']` with A excluded. Negative control
      (fabricated `99` in A's own region) still `fail ['exp/globex-2018:99']`. Pinned by
      test_a_bullet_opening_with_a_later_org_title_and_dates_does_not_anchor_its_region,
      test_a_merged_line_opening_with_a_later_org_title_and_dates_is_reported_not_found,
      test_the_separator_gate_does_not_weaken_a_fabricated_digit_in_the_earlier_region, and the
      parametrized prefix-collision property test.
  - id: 7
    truth: "Check 4 does not silently skip an unanchorable region (no fabricated-digit false negative)."
    status: pass
    evidence: "app/verify/text_checks.py:93-116 collects `unanchored` and returns `_warn` naming the entry with fail precedence; independent repro (empty title + fabricated 99) returns `warn offending=['exp/acme-2019']`."
  - id: 8
    truth: "A CV that fails verification is blocked (not downloadable), and no code path auto-repairs it."
    status: pass
    evidence: "app/pipeline/tailor.py:289 ('deliberately no repair path'); app/api/tailoring.py:494-535 serves only `ok_only=True` (app/db/repositories/cv_artifact_repo.py:174,192); tests/verify/test_block_no_repair.py green."
  - id: 9
    truth: "The verified CV PDF can be previewed inline and downloaded (?download=1); no served path is built from request text."
    status: pass
    evidence: "app/api/tailoring.py:526-535 (stored pdf_path, integer-derived filename); tests/api/test_cv_pdf_route.py green."
  - id: 10
    truth: "The four bullet ops and ReorderSection.section_id ground ids against their id sets, raising UnknownIdError on a non-family id."
    status: pass
    evidence: "app/domain/cv.py; tests/domain/test_patch_ops.py green."
  - id: 11
    truth: "Compile route honours tailoring_enabled=False with 409 tailoring_disabled before load_facts."
    status: pass
    evidence: "app/api/tailoring.py; tests/api/test_tailoring_review.py green."
  - id: 12
    truth: "A raised complete_structured transport error writes exactly one purpose=tailor status=error row, releases the in-flight slot, and surfaces as a typed 502."
    status: pass
    evidence: "app/pipeline/tailor.py:241-256; app/api/tailoring.py:387-392; tests green."
  - id: 13
    truth: "Region start is an org-first + org/title-separator structural boundary: `_entry_lines` requires `startswith(org_needle)`, title presence, the dash separator, and date adjacency."
    status: pass
    evidence: "app/verify/numbers.py:214-226 (`:217` org-first, `:219` separator conjunct, `:221-223` date adjacency); `_dash_fold` `:69-82` keeps one `-` per dash run. Independent repro: a no-separator org-first bullet is rejected (`_dash_fold` = 'acmeseniorengineer...' does not start with 'acme-')."
  - id: 14
    truth: "The region-end bound ends an anchored region by containment against a later unanchored entry's org/title/date-range, never below its own header, with the anchored entry's own date line excluded by line position."
    status: pass
    evidence: "app/verify/numbers.py:361-400 (`end = max(position + 1, min(end, candidate_index))`; positional `excluded_indices`; containment). Merged / digit-bearing / identical-date shapes return `warn`; own-content shapes still `fail ['exp/acme-2018:99']`."
  - id: 15
    truth: "The numbers.py prose makes no claim the code does not deliver: the residual is stated honestly and fail-closed."
    status: pass
    evidence: >-
      numbers.py:169-183 states: a full-header reproduction IS taken as the region start and a surplus
      digit there is a hard `fail` (not a warn); the gate is per-entry MONOTONE (a dropped/normalised
      separator degrades to `found=False` + visible `warn`, never a silent skip); and 'It is not, however,
      a global no-false-fail guarantee', with the compound cursor case subsumed by the residual.
      Independently reproduced: full-header bullet -> `fail ['exp/acme-2019:99']`; real header without
      separator -> `warn ['exp/acme-2018']` (found=False); `grep` for the old false-guarantee phrases
      ('warn instead', 'limits a neighbour', 'cannot carry', 'impossible') -> no match. Ceiling pinned by
      test_a_bullet_reproducing_a_full_header_is_the_documented_hard_fail_ceiling.
  - id: 16
    truth: "VERIFIER_VERSION is a single 1.0.5 bump; Alembic head is 0005 (pre-existing) and this work changes no persisted shape."
    status: pass
    evidence: "app/verify/base.py:22 `VERIFIER_VERSION = '1.0.5'`; `grep -rn '1.0.[0-4]' app tests` against verifier -> no match; alembic/versions highest is `0005_cv_drafts.py` (added by quick task 260929-m1j, not by this work); `da06178..HEAD` touches no alembic path. The prior report's `0004` was stale, not a regression."
  - id: 17
    truth: "A tailored RenderPlan compiles through the real pinned Tectonic engine and its extracted pypdf text passes the real Layer-2 checks."
    status: present_behavior_unverified
    evidence: "Real path present and wired (app/pipeline/tailor.py); no test in this environment exercises the real engine/extraction (Tectonic absent by design D-69). See behavior_unverified_items."
  - id: 18
    truth: "The gap-closure changed set is exactly the five declared paths (two modules, two fixtures, one test file)."
    status: pass
    evidence: "`git diff --name-status da06178~1..HEAD` -> app/verify/base.py (M), app/verify/numbers.py (M), tests/verify/test_numbers.py (M), tests/fixtures/verify/org_first_bullet_extract.txt (A), tests/fixtures/verify/org_first_merge_extract.txt (A). Matches 06-REVIEW.md files_reviewed_list."
gaps: []
deferred:
  - truth: "A failed CV cannot be ATTACHED to an application (the attach half of TAIL-05)."
    addressed_in: "Phase 7"
    evidence: "ROADMAP Phase 7 success criterion 3: 'every application links to the exact verified CV artefact that was sent'; the `ok_only=True` repository predicate is the cross-phase contract Phase 7's attach query consumes."
advisory: []
behavior_unverified_items:
  - truth: "A tailored RenderPlan compiles through the real pinned Tectonic engine and its extracted pypdf text passes the real Layer-2 checks."
    test: "In the container (`docker compose run --rm app pytest -m latex`, or generate + compile a scored listing), compile a tailored plan with the real engine and confirm a PDF plus a passing merged verification_json."
    expected: "A real PDF is produced and the merged VerificationResult passes (or reports only warn-tier checks)."
    why_human: >-
      Tectonic is absent from this host by design (D-69); the hermetic lane overrides the engine with a stub
      writing a canned PDF and monkeypatches `extract_pdf_text` to a committed fixture. Presence and wiring
      of the real path are verified by code reading (app/pipeline/tailor.py), but no test in this
      environment exercises the real engine/extraction behaviour on a tailored plan.
coincidental_reliance_items: []
human_verification:
  - test: "Real-engine tailored compile"
    expected: "In the container (`docker compose run --rm app pytest -m latex`, or generate + compile a scored listing), a real PDF is produced and the persisted merged `verification_json` passes (or reports only warn-tier checks)."
    why_human: "Tectonic is absent on this host by design (D-69); the hermetic lane stubs the engine and extraction."
  - test: "Fail-vs-warn legibility and block-as-outcome"
    expected: "Open the tailoring review and a blocked state; a failing check is visually distinct from a warning, and the block reads as a reviewable outcome with a clear recovery."
    why_human: "Visual/UX behaviour cannot be settled by grep or the hermetic suite."
---

# Phase 6: Tailoring + Verification — Verification Report

**Phase Goal:** A tailored, verified CV PDF the user can preview and download — shipped with its verification gate, never before it.
**Verified:** 2026-09-30T12:02:22Z
**Status:** human_needed
**Re-verification:** Yes — round-5, after the `da06178` / `3b3842b` / `5a667ec` gap closure (truths 6 and 15)

**MVP-mode note:** ROADMAP.md marks Phase 6 `mode: mvp`, but the ROADMAP goal text is not in
user-story form. A valid story was obtained from the plan objective: *"As a job seeker working a
ranked queue, I want to turn one listing into a CV tailored to it, so that I can apply with a CV
shaped to that job without risking a claim I cannot stand behind."* User Flow Coverage uses that
outcome clause.

## Scope of this re-verification

The gap-closure commits changed exactly five paths (`app/verify/numbers.py`, `app/verify/base.py`,
`tests/verify/test_numbers.py`, and two new `tests/fixtures/verify/org_first_*.txt`). Full
verification was applied to the two previously-failing truths (6 and 15); the other truths received
quick regression and the full hermetic suite is green. Git state confirmed: HEAD `5a667ec`; the three
quick tasks (260929-m1j, 260929-pan, 260930-lay) landed between the previous verification and this
one; the gap-closure commits are `da06178`, `3b3842b`, `5a667ec`.

## User Flow Coverage

| Step | Expected | Evidence in codebase | Status |
| ---- | -------- | -------------------- | ------ |
| Outcome clause: apply without risking an unsupported claim | Gate blocks fabrication; valid CVs verify and are previewable/downloadable | Canary `tests/verify/test_no_free_text_path.py`; ok-only download predicate `app/db/repositories/cv_artifact_repo.py:174,192`; `check_metric_containment` with the org-first + separator anchor (numbers.py:214-226) | ✓ VERIFIED |
| Open page → generate → review → compile → download | Each step reachable with the tailoring gate | app/api/tailoring.py routes; `_tailoring_review.html`; tests/api/test_tailoring_review.py, test_cv_pdf_route.py green | ✓ VERIFIED |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | One typed patch from one structured call, one audit row, no artifact | ✓ VERIFIED | `app/pipeline/tailor.py:217-256`; suite green |
| 2 | Typed patch over enumerated IDs, no free-text on PDF path, bullets immutable | ✓ VERIFIED | `app/domain/cv.py:401-441,578,691-713`; canary green |
| 3 | Preview + change log before compiling; drops listed with a reason | ✓ VERIFIED | `_tailoring_review.html`; `tests/api/test_tailoring_review.py` |
| 4 | Gate checks with correct severities (metric_containment can fail; 8/9 warn-only) | ✓ VERIFIED | `app/verify/text_checks.py:104-169` |
| 5 | Digit-bearing locations do not false-fail check 4 | ✓ VERIFIED | `app/verify/numbers.py:199-200`; test green |
| 6 | **Check 4 does not false-fail a valid CV when an earlier bullet names a later entry's org + title (incl. org-first + merge shapes)** | ✓ VERIFIED | Separator conjunct `numbers.py:219`; repro shape 1 `pass`, shape 2 `warn ['exp/acme-2019']`; control `fail ['exp/globex-2018:99']` |
| 7 | Check 4 does not silently skip an unanchorable region | ✓ VERIFIED | `app/verify/text_checks.py:93-116`; repro `warn ['exp/acme-2019']` |
| 8 | Failing CV blocked (not downloadable); no auto-repair | ✓ VERIFIED | `app/pipeline/tailor.py:289`; `ok_only=True` at `app/api/tailoring.py:494-535` |
| 9 | Preview inline + `?download=1`; path never built from request text | ✓ VERIFIED | `app/api/tailoring.py:526-535`; `tests/api/test_cv_pdf_route.py` |
| 10 | Four bullet ops + `ReorderSection.section_id` grounded → `UnknownIdError` | ✓ VERIFIED | `app/domain/cv.py`; `tests/domain/test_patch_ops.py` |
| 11 | Compile route honours `tailoring_enabled=False` with 409 | ✓ VERIFIED | `app/api/tailoring.py`; review tests |
| 12 | Transport error → one `purpose=tailor`,`status=error` row, slot released, typed 502 | ✓ VERIFIED | `app/pipeline/tailor.py:241-256`; `app/api/tailoring.py:387-392` |
| 13 | Org-first + separator + title + date-adjacency region start (`_dash_fold`) | ✓ VERIFIED | `app/verify/numbers.py:69-82,214-226`; no-separator bullet rejected |
| 14 | Region-end containment bound, never below header, own date line positional | ✓ VERIFIED | `app/verify/numbers.py:361-400`; merged/digit-header/identical-date → `warn`; own-content → `fail` |
| 15 | **No false guarantee in prose; residual honest and fail-closed** | ✓ VERIFIED | `numbers.py:169-183`; repro full-header `fail ['exp/acme-2019:99']`, dropped-separator header `warn ['exp/acme-2018']`; no false-guarantee phrase remains |
| 16 | `VERIFIER_VERSION` single `1.0.5` bump; Alembic head `0005`; no persisted shape change | ✓ VERIFIED | `app/verify/base.py:22`; `grep` clean; `alembic/versions` highest `0005_cv_drafts.py` (pre-existing) |
| 17 | Real Tectonic engine compiles a tailored plan; extracted text passes real Layer-2 | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Path wired; Tectonic absent by design (D-69) — `behavior_unverified_items` |
| 18 | Gap-closure changed set is exactly the five declared paths | ✓ VERIFIED | `git diff --name-status da06178~1..HEAD` → 5 paths; matches `06-REVIEW.md` |

**Score:** 17/18 truths verified (0 failed; 1 present, behavior-unverified: truth 17).

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | A failed CV cannot be ATTACHED to an application (attach half of TAIL-05) | Phase 7 | ROADMAP Phase 7 SC3: "every application links to the exact verified CV artefact that was sent" |

### Advisory (New Scope, Unevidenced)

None — the previously new-scope concern (the org-first residual) is now closed on the code, and the
documented hard-fail ceiling is a scoped, fail-closed residual rather than new scope.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/verify/numbers.py` | Org-first + separator region start; region-end bound; honest residual | ✓ VERIFIED | `_dash_fold` `:69-82`; separator conjunct `:219`; bound `:361-400`; residual `:169-183` |
| `app/verify/base.py` | `VERIFIER_VERSION == "1.0.5"` | ✓ VERIFIED | `:22`; no `1.0.[0-4]` in app/tests |
| `app/verify/text_checks.py` | Fail-closed visible `warn` for unanchorable region; fail precedence | ✓ VERIFIED | `:93-116` |
| `tests/fixtures/verify/org_first_bullet_extract.txt` | Shape-1 literal repro string | ✓ VERIFIED | committed (tracked) |
| `tests/fixtures/verify/org_first_merge_extract.txt` | Shape-2 merged repro string | ✓ VERIFIED | committed (tracked) |
| `tests/verify/test_numbers.py` | Literal, merge, negative-control, prefix-collision property, ceiling tests | ✓ VERIFIED | T1–T4 + ceiling at `:947,:993,:1033,:1106,:1133`; `tests/verify` 97 passed |
| Migration | none from this work | ✓ VERIFIED | Alembic head `0005` pre-existing; no alembic path in the changed set |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `cv.tex.jinja:61` (ORG --- TITLE) | `_entry_lines` separator conjunct | `dash_lines[index].startswith(org_dash + '-')` | WIRED | `app/verify/numbers.py:219`; org-first bullet rejected, real header accepted |
| later unanchored entry org/title/date-range | region-end bound | containment `any(needle in line ...)` | WIRED | `app/verify/numbers.py:361-400`; merged/digit-header/identical-date → `warn` |
| `region_token_report` `found=False` | `check_metric_containment` warn | explicit `unanchored` collection | WIRED | `app/verify/text_checks.py:93-116` |
| residual docstring | actual bound disposition | prose claim | ✓ HONEST | Full-header → `fail` (stated); dropped-separator → `warn` (stated); no false guarantee |
| `VERIFIER_VERSION` | `VerificationResult.verifier_version` → persisted `verification_json` | `base.py:22,50` | WIRED | 1.0.5 |
| `latest_for_listing(ok_only=True)` | download route | SQL `compile_status == "ok"` | WIRED | `cv_artifact_repo.py:174,192`; `app/api/tailoring.py:494-535` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| check-4 region report | `RegionReport.candidates` / `.allowed` | `region_token_report(plan, extracted_text)` | Yes — real extraction (fixture in hermetic lane) | ✓ FLOWING |
| `check_metric_containment` outcome | `CheckResult.status` / `.offending` | region reports + allowed sets | Yes | ✓ FLOWING |
| download | `record.pdf_path` | `ok_only=True` SQL selection | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| `tests/verify` lane | `.venv/bin/python -m pytest -q tests/verify` | `97 passed in 4.02s` | ✓ PASS |
| Full hermetic suite | `.venv/bin/python -m pytest -q` | `1533 passed, 14 deselected, 2 xfailed in 238.16s` | ✓ PASS |
| Truth 6 shape 1 — org-first bullet, no separator | independent repro | `found [True, True]`, `pass` | ✓ PASS |
| Truth 6 shape 2 — merge beginning with later org, no separator at start | independent repro | `found [True, False]`, `warn ['exp/acme-2019']`, A not named | ✓ PASS |
| Truth 6 negative control — fabricated `99` in A's own region | independent repro | `fail ['exp/globex-2018:99']` | ✓ PASS |
| Truth 15 ceiling — full-header reproduction | independent repro | `fail ['exp/acme-2019:99']` (documented hard fail) | ✓ PASS |
| Truth 15 — real header loses separator | independent repro | `found=False`, `warn ['exp/acme-2018']` | ✓ PASS |
| `_dash_fold` separator signature | independent repro | header `'acme-seniorengineer2019-01-2019-12'` vs no-separator bullet `'acmeseniorengineer2019-01-2019-12'` | ✓ PASS |
| Base fixture regression | `verify_text(...)` | `passed=True`, `verifier_version=1.0.5` | ✓ PASS |
| Real-engine latex lane | `.venv/bin/python -m pytest -m latex` | cannot run on host — Tectonic absent (D-69) | ? SKIP |

Repro shapes (constructed two-entry `RenderPlan`, no repo file modified):

```
shape 1 (org-first bullet, no separator):
  A: Globex Inc / Engineer / 2018-01 -- 2018-12, bullet "Acme Senior Engineer 2019-01 -- 2019-12 cut 5 incidents"
  text: "Globex Inc --- Engineer" / "2018-01 -- 2018-12" / <bullet> / "Acme --- Senior Engineer" / "2019-01 -- 2019-12" / "Led 7 people"
  -> region found [True, True], B candidates ['7'] -> metric_containment: pass

shape 2 (extractor merge; merged line begins with client org):
  A: Self / Consultant / 2018-01 -- 2018-12, bullet "Acme Senior Engineer contract -- delivered 5 projects Acme --- Senior Engineer"
  text: "Self --- Consultant" / "2018-01 -- 2018-12" / <bullet> / "2019-01 -- 2019-12" / "Led 7 people"
  -> found [True, False] -> metric_containment: warn ['exp/acme-2019']   (A not named)

control (fabricated 99 in A's own region):  -> fail ['exp/globex-2018:99']
ceiling (bullet reproduces the FULL header): -> fail ['exp/acme-2019:99']   (documented residual)
dropped separator on a real header:          -> found=False, warn ['exp/acme-2018']
```

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes and no PLAN-declared probes exist for this phase. Step 7c: NOT APPLICABLE.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| TAIL-01 | 06-01, 06-07, 06-09 | Generate a CV tailored to a specific listing | ✓ SATISFIED | one call → one patch; generate route; off-switch guard; typed 502 |
| TAIL-02 | 06-01, 06-09 | Typed patch over enumerated IDs, no free-text on the PDF path | ✓ SATISFIED | schema + canary + raised-error audit row |
| TAIL-03 | 06-01 | Never rewrites/invents claims; bullet text immutable | ✓ SATISFIED | carried-through `Bullet` objects; canary test |
| TAIL-04 | 06-02, 06-05, 06-08, 06-10, 06-11 | Verification gate checks the compiled PDF for unsupported content | ✓ SATISFIED | org-first + separator anchor (truths 6/13), region-end bound (truth 14), fail-closed warn (truth 7), honest residual (truth 15); `tests/verify` 97 passed |
| TAIL-05 | 06-04 | Failed CV blocked; cannot be downloaded or attached | ✓ SATISFIED (download) / DEFERRED (attach → Phase 7) | `ok_only=True` SQL + route; attach is Phase 7 |
| TAIL-06 | 06-02, 06-03 | Verification never auto-repairs — it blocks | ✓ SATISFIED | no repair branch; tests |
| TAIL-07 | 06-03 | Review the tailored CV and change log before compiling | ✓ SATISFIED | review route/template; guard; tests |
| TAIL-08 | 06-03, 06-06 | Anything dropped is listed explicitly with a reason | ✓ SATISFIED | `dropped_bullets` struck + reason; phantom-change path closed |
| UI-05 | 06-04, 06-07 | Preview and download the tailored CV PDF | ✓ SATISFIED | inline + `?download=1`; tests |

All 9 phase requirement IDs appear in at least one plan's `requirements:` field. No ORPHANED
requirements. `REQUIREMENTS.md`'s `TAIL-04` traceability mark may now be set to Complete (this
re-verification verifies it); the Phase-7 attach half of TAIL-05 remains future work.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `app/verify/numbers.py` | 169-183 | Documented hard-fail ceiling: a bullet reproducing the FULL header still anchors and hard-fails (structurally irreducible at line granularity) | ℹ️ Info (scoped, fail-closed) | A contrived bullet that literally opens `<org> --- <title> <dates>` can block a valid CV; documented and fail-closed, not a false pass |
| `tests/verify/test_numbers.py` | 10,524,578,686 | Pre-existing `ruff` I001/E501 style errors on lines untouched by this work | ℹ️ Info | Cosmetic; not introduced by the gap closure |

No `TBD`/`FIXME`/`XXX` debt markers were found in the phase's modified files. **No blocking check was
weakened** — `metric_containment` still hard-fails an anchored surplus; `page_budget`/`layout_ats`
remain the only warn-only checks; a warn never blocks; `novel_metric_extract.txt` still fails
`['exp/northwind-labs-2021:3.12']`. **No new dependency added.** **The gap-closure commits touch no
Alembic path.**

### Human Verification Required

1. **Real-engine tailored compile** — In the container (`docker compose run --rm app pytest -m latex`,
   or generate + compile a scored listing), compile a tailored plan with the real pinned Tectonic
   engine; confirm a real PDF and the persisted merged `verification_json`. The hermetic lane stubs the
   engine and extraction (D-69).
2. **Fail-vs-warn legibility and block-as-outcome** — Open the tailoring review and the blocked state;
   confirm a failing check is visually distinct from a warning and that the block reads as a reviewable
   outcome with a clear recovery.

### Gaps Summary

Round-5 closes the two surviving gaps from the round-4 report, verified independently on the code
rather than on the summary.

**Truth 6 — CLOSED.** `da06178` adds `_dash_fold` (numbers.py:69-82) and a separator conjunct to
`_entry_lines` (numbers.py:219): a region now starts only when the line also carries the template's
`ORG --- TITLE` dash separator (`cv.tex.jinja:61`), in addition to org-first, title presence and date
adjacency. I reproduced both original repro shapes at HEAD: the org-first bullet
(`Acme Senior Engineer 2019-01 -- 2019-12 cut 5 incidents`) now yields `pass`, and the extractor-merge
line (`Acme Senior Engineer contract -- delivered 5 projects Acme --- Senior Engineer`) now yields a
visible `warn ['exp/acme-2019']` naming the unanchored entry, with the earlier entry not charged. The
mechanism is confirmed by `_dash_fold`: a real header folds to `acme-<title>…` (observable separator),
while a no-separator org-first line folds to `acme<title>…` and is refused. The negative control — a
genuinely fabricated `99` inside the earlier entry's own region — still hard-fails
(`fail ['exp/globex-2018:99']`), so the accept-side fix was not bought by weakening the block.

**Truth 15 — CLOSED.** The rewritten residual (numbers.py:169-183) is honest and fail-closed. It
states that a body line reproducing the FULL header is structurally indistinguishable from a real
header at line granularity and IS taken as the region start, where a surplus digit is a hard `fail`
(not a warn); that the gate is per-entry monotone, so a dropped/normalised separator on a real header
degrades to `found=False` and a visible `warn` naming the entry, never a silent skip; and explicitly
that it is "not a global no-false-fail guarantee", subsuming the compound cursor case. I reproduced
all three dispositions: full-header reproduction → `fail ['exp/acme-2019:99']`; real header without
separator → `warn ['exp/acme-2018']`; and `grep` confirms the old false-guarantee phrasing is gone.
The full-header ceiling is now pinned by
`test_a_bullet_reproducing_a_full_header_is_the_documented_hard_fail_ceiling`. The only remaining
behaviour of note is that documented, fail-closed ceiling — a contrived full-header bullet can still
block a valid CV, which is stated rather than hidden and cannot silently pass.

Criterion E is satisfied: `06-REVIEW.md` is `clean` (0 critical, 0 warning, 5 info, all resolved) at
`3b3842b`, and the changed set is exactly the five declared paths. Truths 16 and 18 are restated at
HEAD: `VERIFIER_VERSION` is a single `1.0.5` bump and the Alembic head is `0005` (pre-existing from
quick task 260929-m1j — the prior report's `0004` was stale, not a regression).

No gaps remain. The only open items are the two container-only checks below (real Tectonic compile and
fail-vs-warn legibility), which is why the status is `human_needed`, not `passed`.

---

_Verified: 2026-09-30T12:02:22Z_
_Verifier: the agent (gsd-verifier)_
