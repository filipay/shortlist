---
phase: 06-tailoring-verification
verified: 2026-09-25T16:38:29Z
status: gaps_found
score: 15/18 must-haves verified
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
  - tests/verify/test_numbers.py
  - tests/verify/test_text_checks.py
covered_digest: "v1:sha256:f56e9e70d9e01b6ec6586761856b6d23d98cb7411bdc006d6648c53476878144"
behavior_unverified: 1
overrides_applied: 0
requirements_verified:
  - TAIL-01
  - TAIL-02
  - TAIL-03
  - TAIL-05
  - TAIL-06
  - TAIL-07
  - TAIL-08
  - UI-05
re_verification:
  previous_status: gaps_found
  previous_score: 11/12
  gaps_closed:
    - "Truth 7 / WR-01 (unanchorable check-4 region silently skipped): CLOSED on the code — `check_metric_containment` collects every `found=False` region and returns a visible `warn` naming the entry (app/verify/text_checks.py:93-116); fail precedence preserved."
    - "Criterion E: the scoped re-review is CLEAN — 06-REVIEW.md `status: clean`, critical 0, warning 0, info 3 (reviewed 2026-09-25T16:00:12Z)."
    - "06-11 mechanics all present: `_entry_lines` requires `line.startswith(org_needle)` plus title presence plus date adjacency (numbers.py:173-178); region-end bound by containment against a later unanchored entry's org/title/date-range, never below its own header, own date line excluded by position (numbers.py:314-352); `VERIFIER_VERSION == '1.0.4'` (base.py:22); Alembic head 0004."
  gaps_remaining:
    - "Truth 6 residual: a valid CV still false-fails check 4 when an earlier bullet BEGINS with a later entry's org AND carries its title with an adjacent date-range — reproduced `fail ['exp/acme-2019:5']` and `fail ['exp/b:5']` on a correct CV."
    - "The `_entry_lines` docstring (numbers.py:135-141) claims the region-end bound turns that residual into a visible `warn`; it returns `fail` — a false guarantee in prose (AGENTS.md convention 6) and a violation of the 06-11 `transparency` prohibition."
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
    evidence: "app/verify/text_checks.py:104-116, :134-143, :146-169; tests/verify/test_text_checks.py green."
  - id: 5
    truth: "Digit-bearing entry locations (Dublin 2, Eircode, Remote (GMT+1)) do not false-fail check 4."
    status: pass
    evidence: "app/verify/numbers.py:199-200 folds location into allowed; test_a_digit_bearing_location_is_not_a_surplus_candidate green."
  - id: 6
    truth: "Check 4 does not false-fail a valid CV when an earlier bullet names a later entry's org AND title (06-11 org-first boundary; the documented residual must not hard-fail the correct CV)."
    status: fail
    evidence: "Mid-line embedding fixed (variant-1 repro `pass`: app/verify/numbers.py:173). Residual NOT fixed: an earlier bullet that BEGINS with the later org + title + adjacent date-range anchors that region and check 4 charges the earlier grounded digit to it. Independent repro: A bullet `Acme Senior Engineer 2019-01 -- 2019-12 cut 5 incidents` -> `fail ['exp/acme-2019:5']`; docstring's own cited extractor-merge shape -> `fail ['exp/b:5']`. See Gaps."
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
    truth: "The 06-11 org-first anchor: `_entry_lines` requires the squashed candidate line to start with the org needle in addition to title presence and date adjacency."
    status: pass
    evidence: "app/verify/numbers.py:173 `if not line.startswith(org_needle) or title_needle not in line: continue`; :175-178 date adjacency. Variant-1 repro `pass`."
  - id: 14
    truth: "The 06-11 region-end bound: an anchored region ends by containment against a later unanchored entry's org/title/date-range, never below its own header, with the anchored entry's own date line excluded by line position."
    status: pass
    evidence: "app/verify/numbers.py:314-352 (`end = max(position + 1, min(end, candidate_index))`; positional `excluded_indices` at :319-328; containment at :350). Merged / digit-bearing / identical-date shapes return `warn` with no false fail; own-content shapes still `fail ['exp/acme-2018:99']`."
  - id: 15
    truth: "No false guarantee remains in the region-segmentation prose (the code delivers what the docstring claims)."
    status: fail
    evidence: "app/verify/numbers.py:135-141 claims the region-end bound 'limits a neighbour to a visible warn instead of a false fail' for the org-first residual; independently reproduced `fail ['exp/b:5']`. Violates the 06-11 prohibition (transparency) and AGENTS.md convention 6. Note: the must-have's ast scan for never/cannot/impossible is clean — the offending claim is a positive disposition claim, not a negative absolute."
  - id: 16
    truth: "Single VERIFIER_VERSION bump to 1.0.4 with no 1.0.3 remaining; Alembic head 0004; no persisted shape changed."
    status: pass
    evidence: "app/verify/base.py:22; `grep -rn '1.0.3' app tests` -> no match; alembic/versions highest `0004_ranking_config.py`."
  - id: 17
    truth: "A tailored RenderPlan compiles through the real pinned Tectonic engine and its extracted pypdf text passes the real Layer-2 checks."
    status: present_behavior_unverified
    evidence: "Real path present and wired (app/pipeline/tailor.py); no test in this environment exercises the real engine/extraction (Tectonic absent by design D-69). See behavior_unverified_items."
  - id: 18
    truth: "06-11 changed set is exactly the seven declared paths (two modules, four fixtures, one test file)."
    status: pass
    evidence: "git diff HEAD~4..HEAD~2 (7a168a9, 6711384) shows those paths; `git ls-files` for the seven paths -> 7."
gaps:
  - truth: "Check 4 does not false-fail a valid CV when an earlier bullet names a later entry's org AND title (the 06-11 org-first boundary; the documented line-start residual must not hard-fail the correct CV)."
    status: failed
    reason: >-
      Mid-line embedding is genuinely fixed and verified: the variant-1 repro returns `pass`, and the
      region-end bound correctly downgrades the merged/digit-bearing/identical-date neighbour shapes to a
      visible `warn`. But the org-first boundary still admits a body line that BEGINS with the later entry's
      org. If that line also carries the title with an adjacent date-range it is taken as the region start
      (numbers.py:173-180), and check 4 charges the earlier entry's grounded digit to the later region.
      Independently reproduced two ways on HEAD (no source/test modified):
      (1) `Acme Senior Engineer 2019-01 -- 2019-12 cut 5 incidents` as A's bullet line ->
      regions found `[True, True]`, B candidates `['5','7']` -> `fail ['exp/acme-2019:5']` — the exact
      offending string of the prior gap truth 6.
      (2) the docstring's own cited example, an extractor line-merge of A's bullet with B's following
      header where A's bullet begins with the client org (`Acme Senior Engineer contract -- delivered 5
      projects Acme --- Senior Engineer`) -> `fail ['exp/b:5']`. The mid-line control for the same merge
      correctly returns `warn ['exp/b']`, proving the org-first position is the only differentiator.
      The digit is grounded in A's own bullet, so the CV is valid; D-118's only recovery is a fresh tailor
      that deterministically re-runs the same predicate, so preview/download are dead for that CV. The
      06-11 plan documents this shape as a residual in `flagged_assumptions` ("no demonstrated
      reproduction produces such a line"), but a reproduction does produce it, and the code's docstring
      states a disposition (warn) the code does not deliver.
    artifacts:
      - path: "app/verify/numbers.py"
        issue: "`_entry_lines` org-first anchor (:173-180) is satisfied by a body line beginning with the org; the region-end bound (:314-352) only runs for later UNANCHORED entries, so it cannot fire when the neighbour becomes anchored at the residual line."
      - path: "tests/verify/test_numbers.py"
        issue: "No test pins the documented org-first residual (06-REVIEW.md IN-03); the property tests embed the org mid-line only."
    missing:
      - "Make the region start a boundary a body line cannot satisfy at line granularity — e.g. additionally require the header separator (`---`/em-dash) that the template emits, as the prior verifier and Phase-6 reviewer both offered — OR explicitly pin the residual with a test and correct the docstring to state the actual disposition (hard-fail, not warn). Whichever route: `06-REVIEW.md` must be re-run to confirm no unresolved warning on the changed files (criterion E)."
  - truth: "No false guarantee remains in the region-segmentation prose (the code delivers what the docstring claims)."
    status: failed
    reason: >-
      `_entry_lines` docstring (app/verify/numbers.py:135-141) states that for the line-start residual
      "the region starts there; region_token_report's region-end bound is what then limits a neighbour to a
      visible `warn` instead of a false `fail`." Independently reproduced: the bound does not fire (the
      neighbour is anchored, not unanchored) and the result is `fail ['exp/b:5']`. This is a guarantee the
      code does not deliver (AGENTS.md convention 6) and directly violates the 06-11 plan's `transparency`
      prohibition "MUST NOT leave an absolute guarantee in the region-segmentation prose that the code does
      not deliver" (status: unresolved). `06-REVIEW.md` IN-03 rests on the same false assumption ("the
      check does not hard-fail the correct CV"), so it is not a rebuttal — the reviewer did not exercise
      the shape.
    artifacts:
      - path: "app/verify/numbers.py"
        issue: "Docstring at :135-141 overstates the region-end bound's coverage of the org-first residual."
    missing:
      - "Correct the docstring to state the real disposition, or remove the bound claim; add the pinning test (IN-03)."
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
**Verified:** 2026-09-25T16:38:29Z
**Status:** gaps_found
**Re-verification:** Yes — after round-4 gap closure (06-11) fixing the check-4 region anchor (WR-02 residual)

**MVP-mode note:** ROADMAP.md marks Phase 6 `mode: mvp`, but the ROADMAP goal text is not in
user-story form (`user-story.validate` → `valid: false`). A valid story was obtained from the plan
objective: *"As a job seeker working a ranked queue, I want to turn one listing into a CV tailored to
it, so that I can apply with a CV shaped to that job without risking a claim I cannot stand behind."*
(`user-story.validate` → `valid: true`). User Flow Coverage uses that outcome clause.

## Scope of this re-verification

06-11 changed exactly seven paths (`app/verify/numbers.py`, `app/verify/base.py`,
`tests/verify/test_numbers.py`, and four new `tests/fixtures/verify/*.txt`). Per re-verification rules
the prior FAILED truth (6) and the criterion-E gap receive full verification; the prior PASSED truths
receive quick regression and the full hermetic suite is green. Git state confirmed: HEAD `b517876`;
06-11 code commits `7a168a9` and `6711384`, metadata `4f4c8a4`.

## User Flow Coverage

| Step | Expected | Evidence in codebase | Status |
| ---- | -------- | -------------------- | ------ |
| Outcome clause: apply without risking an unsupported claim | Gate blocks fabrication; valid CVs verify and are previewable/downloadable | Canary `tests/verify/test_no_free_text_path.py`; ok-only download predicate `app/db/repositories/cv_artifact_repo.py:174,192`; `check_metric_containment` — **but check 4 still false-fails a valid CV whose earlier bullet begins with a later entry's org** | ✗ FAILED |
| Open page → generate → review → compile → download | Each step reachable with the tailors gate | app/api/tailoring.py routes; `_tailoring_review.html`; tests/api/test_tailoring_review.py, test_cv_pdf_route.py green | ✓ VERIFIED (regression) |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | One typed patch from one structured call, one audit row, no artifact | ✓ VERIFIED | `app/pipeline/tailor.py:217-256`; suite green |
| 2 | Typed patch over enumerated IDs, no free-text on PDF path, bullets immutable | ✓ VERIFIED | `app/domain/cv.py:401-441,578,691-713`; canary green |
| 3 | Preview + change log before compiling; drops listed with a reason | ✓ VERIFIED | `_tailoring_review.html`; `tests/api/test_tailoring_review.py` |
| 4 | Gate checks with correct severities (metric_containment can fail; 8/9 warn-only) | ✓ VERIFIED | `app/verify/text_checks.py:104-116,134-169` |
| 5 | Digit-bearing locations do not false-fail check 4 | ✓ VERIFIED | `app/verify/numbers.py:199-200`; test green |
| 6 | **Check 4 does not false-fail a valid CV when an earlier bullet names a later entry's org + title (06-11 org-first; residual must not hard-fail)** | ✗ FAILED | Mid-line fixed; **line-start residual false-fails** — repro `fail ['exp/acme-2019:5']` / `fail ['exp/b:5']`. See Gaps |
| 7 | Check 4 does not silently skip an unanchorable region | ✓ VERIFIED | `app/verify/text_checks.py:93-116`; repro `warn ['exp/acme-2019']` |
| 8 | Failing CV blocked (not downloadable); no auto-repair | ✓ VERIFIED | `app/pipeline/tailor.py:289`; `ok_only=True` at `app/api/tailoring.py:494-535` |
| 9 | Preview inline + `?download=1`; path never built from request text | ✓ VERIFIED | `app/api/tailoring.py:526-535`; `tests/api/test_cv_pdf_route.py` |
| 10 | Four bullet ops + `ReorderSection.section_id` grounded → `UnknownIdError` | ✓ VERIFIED | `app/domain/cv.py`; `tests/domain/test_patch_ops.py` |
| 11 | Compile route honours `tailoring_enabled=False` with 409 | ✓ VERIFIED | `app/api/tailoring.py`; review tests |
| 12 | Transport error → one `purpose=tailor`,`status=error` row, slot released, typed 502 | ✓ VERIFIED | `app/pipeline/tailor.py:241-256`; `app/api/tailoring.py:387-392` |
| 13 | 06-11 `_entry_lines` requires `startswith(org_needle)` + title + date adjacency | ✓ VERIFIED | `app/verify/numbers.py:173-178`; variant-1 repro `pass` |
| 14 | 06-11 region-end bound by containment, never below header, own date line positional | ✓ VERIFIED | `app/verify/numbers.py:314-352`; merged/digit-header/identical-date → `warn`; own-content → `fail` |
| 15 | **No false guarantee remains in the region-segmentation prose** | ✗ FAILED | `app/verify/numbers.py:135-141` claims the bound limits the residual to a `warn`; repro returns `fail`. See Gaps |
| 16 | `VERIFIER_VERSION == "1.0.4"`; no `1.0.3`; Alembic head `0004`; no persisted shape change | ✓ VERIFIED | `app/verify/base.py:22`; grep clean; `alembic/versions` highest `0004` |
| 17 | Real Tectonic engine compiles a tailored plan; extracted text passes real Layer-2 | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Path wired; Tectonic absent by design (D-69) — `behavior_unverified_items` |
| 18 | 06-11 changed set is exactly the seven declared paths | ✓ VERIFIED | `7a168a9`/`6711384` diff; `git ls-files` → 7 |

**Score:** 15/18 truths verified (2 failed: truths 6 and 15; 1 present, behavior-unverified: truth 17).

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | A failed CV cannot be ATTACHED to an application (attach half of TAIL-05) | Phase 7 | ROADMAP Phase 7 SC3: "every application links to the exact verified CV artefact that was sent" |

### Advisory (New Scope, Unevidenced)

None — the only new-scope concern (the org-first residual) is on a changed file and is therefore in
scope and blocking, not advisory.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/verify/numbers.py` | Org-first region start; region-end containment bound; positional own-date exclusion; prose matches code | ⚠️ PARTIAL | `:173-178` org-first ✓; `:314-352` bound ✓; but `:135-141` docstring overstates the bound's coverage of the org-first residual (truth 15) |
| `app/verify/base.py` | `VERIFIER_VERSION == "1.0.4"` | ✓ VERIFIED | `:22`; no `1.0.3` in app/tests |
| `app/verify/text_checks.py` | Fail-closed visible `warn` for unanchorable region; fail precedence | ✓ VERIFIED | `:93-116` |
| `tests/fixtures/verify/org_title_dates_collision_extract.txt` | Variant-1 literal repro string | ✓ VERIFIED | present, read by test |
| `tests/fixtures/verify/org_title_dates_merge_extract.txt` | Variant-2 merged line | ✓ VERIFIED | present, read by test |
| `tests/fixtures/verify/digit_bearing_header_extract.txt` | `3M ---` / `Manager` before dates | ✓ VERIFIED | present, read by test |
| `tests/fixtures/verify/identical_dates_extract.txt` | Shared identical date-range | ✓ VERIFIED | present, read by test |
| `tests/verify/test_numbers.py` | Literal, leak-guard, own-content, org+title+dates property tests | ⚠️ PARTIAL | 6 new tests (15 parametrizations) green; the org-first **line-start** residual (review IN-03) is untested |
| Migration | none | ✓ VERIFIED | Alembic head `0004` |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `cv.tex.jinja:58` (org first) | `_entry_lines` org-first start | `startswith(org_needle)` | WIRED, LEAKY | `app/verify/numbers.py:173`; mid-line blocked, line-start residual passes (truth 6) |
| later unanchored entry org/title/date-range | region-end bound | containment `any(needle in line ...)` | WIRED | `app/verify/numbers.py:350`; merged/digit-header/identical-date → `warn` |
| `region_token_report` `found=False` | `check_metric_containment` warn | explicit `unanchored` collection | WIRED | `app/verify/text_checks.py:93-116` (truth 7 closed) |
| `_entry_lines` residual docstring | actual bound disposition | prose claim | ✗ BROKEN | `:135-141` claims warn; code gives fail (truth 15) |
| `VERIFIER_VERSION` | `VerificationResult.verifier_version` → persisted `verification_json` | `base.py:22,50` | WIRED | 1.0.4 |
| `latest_for_listing(ok_only=True)` | download route | SQL `compile_status == "ok"` | WIRED | `cv_artifact_repo.py:174,192`; `app/api/tailoring.py:494-535` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| check-4 region report | `RegionReport.candidates` / `.allowed` | `region_token_report(plan, extracted_text)` | Yes — real extraction (fixture in hermetic lane) | ✓ FLOWING (residual mis-segmentation, truth 6) |
| `check_metric_containment` outcome | `CheckResult.status` / `.offending` | region reports + allowed sets | Yes | ✓ FLOWING |
| download | `record.pdf_path` | `ok_only=True` SQL selection | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| `tests/verify` lane | `.venv/bin/python -m pytest -q tests/verify` | `89 passed in 12.28s` | ✓ PASS |
| Full hermetic suite | `.venv/bin/python -m pytest -q` | `1265 passed, 14 deselected, 2 xfailed in 522.98s` | ✓ PASS |
| Truth 13 — mid-line org embedding cannot anchor (variant 1) | independent repro | B candidates `['7']`, check `pass` | ✓ PASS |
| Truth 14 — merged header, dates on successor (variant 2) | independent repro | `found [True, False]`, `warn ['exp/acme-2019']` | ✓ PASS |
| Truth 14 — merged header with dates inline | independent repro | `warn ['exp/acme-2019']` | ✓ PASS |
| Negative control — fabricated `99` in A's own region | independent repro | `fail ['exp/globex-2018:99']` | ✓ PASS |
| **Truth 6 residual** — bullet begins with next org+title+dates | independent repro | `fail ['exp/acme-2019:5']` | ✗ FAIL |
| **Truth 6 residual** — extractor merge, bullet begins with client org | independent repro | `fail ['exp/b:5']` | ✗ FAIL |
| Mid-line control for the same merge | independent repro | `warn ['exp/b']` | ✓ PASS |
| Real-engine latex lane | `.venv/bin/python -m pytest -m latex` | cannot run on host — Tectonic absent (D-69) | ? SKIP |

Repro shapes (constructed two-entry `RenderPlan`, no repo file modified):

```
residual 1 (bullet line begins with B org+title+dates):
  A: Globex Inc / Engineer / 2018-01 -- 2018-12, bullet "Acme Senior Engineer 2019-01 -- 2019-12 cut 5 incidents"
  text: "Globex Inc --- Engineer" / "2018-01 -- 2018-12" / <bullet> / "Led 7 people"
  -> regions found [True, True] candidates [[], ['5','7']] -> metric_containment: fail ['exp/acme-2019:5']

residual 2 (docstring's cited extractor line-merge; bullet begins with client org):
  A: Self / Consultant / 2018-01 -- 2018-12, bullet "Acme Senior Engineer contract -- delivered 5 projects"
  text: "Self --- Consultant" / "2018-01 -- 2018-12" / <bullet>+" Acme --- Senior Engineer" / "2019-01 -- 2019-12" / "Led 7 people"
  -> metric_containment: fail ['exp/b:5']      (mid-line control -> warn ['exp/b'])
```

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes and no PLAN-declared probes exist for this phase. Step 7c: NOT APPLICABLE.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| TAIL-01 | 06-01, 06-07, 06-09 | Generate a CV tailored to a specific listing | ✓ SATISFIED | one call → one patch; generate route; off-switch guard; typed 502 |
| TAIL-02 | 06-01, 06-09 | Typed patch over enumerated IDs, no free-text on the PDF path | ✓ SATISFIED | schema + canary + raised-error audit row |
| TAIL-03 | 06-01 | Never rewrites/invents claims; bullet text immutable | ✓ SATISFIED | carried-through `Bullet` objects; canary test |
| TAIL-04 | 06-02, 06-05, 06-08, 06-10, 06-11 | Verification gate checks the compiled PDF for unsupported content | ✗ BLOCKED | Truth 7 closed and 06-11 mechanics correct, but the org-first residual still false-fails a valid CV (truth 6) and the docstring overstates the bound (truth 15) |
| TAIL-05 | 06-04 | Failed CV blocked; cannot be downloaded or attached | ✓ SATISFIED (download) / DEFERRED (attach → Phase 7) | `ok_only=True` SQL + route; attach is Phase 7 |
| TAIL-06 | 06-02, 06-03 | Verification never auto-repairs — it blocks | ✓ SATISFIED | no repair branch; tests |
| TAIL-07 | 06-03 | Review the tailored CV and change log before compiling | ✓ SATISFIED | review route/template; guard; tests |
| TAIL-08 | 06-03, 06-06 | Anything dropped is listed explicitly with a reason | ✓ SATISFIED | `dropped_bullets` struck + reason; phantom-change path closed |
| UI-05 | 06-04, 06-07 | Preview and download the tailored CV PDF | ✓ SATISFIED | inline + `?download=1`; tests |

All 9 phase requirement IDs appear in at least one plan's `requirements:` field. No ORPHANED requirements.
`REQUIREMENTS.md:73` currently checks `TAIL-04` as `[x]` and lists it `Complete` (`:219`) — that
traceability status is **stale**: this re-verification finds TAIL-04 still BLOCKED (see truths 6/15).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `app/verify/numbers.py` | 173-180 | Org-first anchor is a position test a body line can satisfy by beginning with the org — not a discriminator a body line cannot satisfy (AGENTS convention 1) | ⚠️ Warning (blocking per truth 6) | A body line beginning with the next org hijacks that region → false-fail on a valid CV |
| `app/verify/numbers.py` | 135-141 | Docstring claims the region-end bound converts the org-first residual to a `warn`; code returns `fail` (AGENTS convention 6; violates the 06-11 transparency prohibition) | ⚠️ Warning (blocking per truth 15) | False guarantee in prose; suppresses scrutiny of the residual |
| `tests/verify/test_numbers.py` | 521-541, 911-941 | Property tests mutate only the org+title (and org+title+dates mid-line) dimensions, never a line *beginning* with the org (review IN-03) | ℹ️ Info | The residual's ceiling is unpinned |
| `06-REVIEW.md` | 122-132 | IN-03 assumes the residual "does not hard-fail the correct CV"; the assumption is false | ℹ️ Info | The clean review's only coverage of the residual is based on a wrong premise |

No `TBD`/`FIXME`/`XXX` debt markers were found in the phase's modified files. **No blocking check was
weakened** — `metric_containment` still hard-fails an anchored surplus; `page_budget`/`layout_ats`
remain the only warn-only checks; a warn never blocks; `novel_metric_extract.txt` still fails
`['exp/northwind-labs-2021:3.12']`. **No new dependency added. Alembic head is still `0004`.**

### Human Verification Required

1. **Real-engine tailored compile** — In the container (`docker compose run --rm app pytest -m latex`,
   or generate + compile a scored listing), compile a tailored plan with the real pinned Tectonic
   engine; confirm a real PDF and the persisted merged `verification_json`. The hermetic lane stubs the
   engine and extraction (D-69).
2. **Fail-vs-warn legibility and block-as-outcome** — Open the tailoring review and the blocked state;
   confirm a failing check is visually distinct from a warning and that the block reads as a reviewable
   outcome with a clear recovery.

### Gaps Summary

Round-4 gap closure (06-11) delivers all of its specified mechanics, and the previously-failing
criterion E is now satisfied: `06-REVIEW.md` re-run is `clean` (critical 0, warning 0, info 3). Truth 7
remains closed. The two independent WR-02 reproductions from the prior report now pass or warn: the
variant-1 (mid-line org+title+dates) returns `pass`, the merged shapes return `warn` naming the
unanchored entry, and the anchored-surplus negative controls still hard-fail. The single
`VERIFIER_VERSION` bump to `1.0.4` and the unchanged Alembic head `0004` are confirmed.

**Truth 6 — NOT fully closed.** The org-first anchor fixes the *mid-line* class only. A body line that
BEGINS with the later entry's org still satisfies the anchor; with the title and an adjacent date-range
present, it is taken as that entry's region start and check 4 charges the earlier entry's grounded digit
to the later region. I reproduced this on HEAD two ways — the residual bullet shape
(`fail ['exp/acme-2019:5']`, the prior gap's exact offending string) and the docstring's own cited
extractor line-merge example (`fail ['exp/b:5']`) — with the mid-line control for the same merge
correctly returning `warn ['exp/b']`. The digit is grounded in the earlier entry's own bullet, so the CV
is valid; because D-118's only recovery re-runs the same predicate, preview/download are dead for that
CV. The 06-11 plan documents this shape as a residual but asserts "no demonstrated reproduction produces
such a line"; a reproduction does produce it.

**Truth 15 — FAILED.** The `_entry_lines` docstring (`app/verify/numbers.py:135-141`) states the
region-end bound "limits a neighbour to a visible `warn` instead of a false `fail`" for this residual.
The bound only runs for later *unanchored* entries, so it does not fire when the neighbour becomes
anchored at the residual line, and the result is a `fail`. This is a guarantee the code does not deliver
(AGENTS.md convention 6) and violates the 06-11 `transparency` prohibition ("MUST NOT leave an absolute
guarantee in the region-segmentation prose that the code does not deliver", status: unresolved).
`06-REVIEW.md` IN-03 assumes the opposite ("the check does not hard-fail the correct CV") and therefore
is not a rebuttal — the reviewer did not exercise the shape.

A fix direction is available and was offered by both the prior verifier and the Phase-6 reviewer:
require the `---`/em-dash header separator in addition to org-first (a boundary a body line cannot
satisfy at line granularity), or — if the residual is accepted — pin it with a test and correct the
docstring to state the actual disposition. Either way `06-REVIEW.md` must be re-run to confirm no
unresolved warning on the changed files (criterion E). `REQUIREMENTS.md`'s `TAIL-04` "Complete" mark
should be reverted to open.

---

_Verified: 2026-09-25T16:38:29Z_
_Verifier: the agent (gsd-verifier)_
