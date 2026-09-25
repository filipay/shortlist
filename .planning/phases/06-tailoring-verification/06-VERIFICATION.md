---
phase: 06-tailoring-verification
verified: 2026-09-25T10:23:05Z
status: gaps_found
score: 9/12 must-haves verified
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
  - app/api/tailoring.py
  - app/config.py
  - app/db/repositories/cv_artifact_repo.py
  - app/db/repositories/llm_call_repo.py
  - app/domain/cv.py
  - app/main.py
  - app/pipeline/tailor.py
  - app/verify/__init__.py
  - app/verify/base.py
  - app/verify/grounding.py
  - app/verify/numbers.py
  - app/verify/plan_checks.py
  - app/verify/text_checks.py
  - app/web/templates/html/_cv_findings.html
  - app/web/templates/html/_tailoring_review.html
  - app/web/templates/html/listing_detail.html
  - app/web/templates/html/tailoring.html
  - static/vendor/app.css
  - tests/api/test_tailoring_generate.py
  - tests/api/test_tailoring_review.py
  - tests/domain/test_patch_ops.py
  - tests/fixtures/verify/digit_location_extract.txt
  - tests/fixtures/verify/digit_skill_extract.txt
  - tests/pipeline/test_tailor_stage.py
  - tests/verify/fixtures.py
  - tests/verify/test_numbers.py
  - tests/verify/test_text_checks.py
covered_digest: "v1:sha256:e90a0ecc325af770f38b208b6f4022e714b2d7cf4096d2284b66c5a6e64a3c0a"
behavior_unverified: 1
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 9/10
  gaps_closed: []
  gaps_remaining:
    - "Real Tectonic engine + pypdf extraction on a tailored RenderPlan is still behavior-unverified on this dry host (Tectonic absent by design, D-69)."
  regressions: []
gaps:
  - truth: "A valid tailored CV whose earlier bullet names a later entry's org AND title verifies and is previewable/downloadable (check 4 computes no surplus for a correct region)."
    status: failed
    reason: >-
      `_entry_lines` anchors a region on any line that contains BOTH `squash(org)` and
      `squash(title)` as naked substrings (`app/verify/numbers.py:151-156`). A bullet in an
      earlier entry that mentions the later entry's org and a title word on one line still
      matches first, so the later region starts at that bullet line and the earlier entry's
      digit becomes a surplus candidate — check 4 HARD FAILS an otherwise-correct CV, and the
      only recovery (a fresh tailor, D-118) deterministically re-runs the same predicate, so
      preview/download are dead for that CV. This is the residual of the CR-02 defect round 2
      (06-08) claimed to close; independently reproduced here and corroborated by
      `06-REVIEW.md` CR-01 (Critical) and `06-VALIDATION.md` ESC-06-A.
    artifacts:
      - path: "app/verify/numbers.py"
        issue: "`_entry_lines` (lines 120-160, anchor predicate at 151-156) substring-matches org+title; a bullet containing both hijacks the region start."
    missing:
      - "A structural discriminator a bullet cannot satisfy — e.g. require the entry's date-range needle on the candidate line or its successor (`dates_adjacency`), or the `---`/em-dash header separator — and a regression test with two entries at the same employer whose earlier bullet contains the later org+title and a digit (expected: each region keeps its own metrics; `novel_metric_extract.txt` still fails)."
  - truth: "Check 4 catches, or at least surfaces, a fabricated digit in a region it cannot anchor (no silent false negative in the one blocking integrity check)."
    status: failed
    reason: >-
      The strict org-AND-title anchor reports `found=False` whenever no single squashed line
      carries both needles (an empty/all-punctuation `title`, or a long org+title that wraps
      across two extracted lines). `region_token_report` then emits `candidates=[]`
      (`app/verify/numbers.py:249-264`) and `check_metric_containment` skips the region
      (`app/verify/text_checks.py:86-88`), so a fabricated digit inside it passes check 4
      silently. Independently reproduced here (a fabricated `99` passes) and corroborated by
      `06-REVIEW.md` WR-01 and `06-VALIDATION.md` ESC-06-B.
    artifacts:
      - path: "app/verify/numbers.py"
        issue: "`position < 0` → `found=False`, `candidates=[]` (lines 249-264)."
      - path: "app/verify/text_checks.py"
        issue: "`not report.found` skip (lines 86-88) turns an unanchorable region into a silent pass."
    missing:
      - "Either surface an unanchorable region as a visible `warn` (so the operator sees the entry was not metric-checked), or fall back to a collision-resistant anchor (dates-adjacency or `---` separator) before declaring the region absent; add a test asserting the integrity consequence. Do NOT restore the org-only substring anchor."
deferred:
  - truth: "A failed CV cannot be ATTACHED to an application (the attach half of TAIL-05)."
    addressed_in: "Phase 7"
    evidence: "ROADMAP Phase 7 success criterion 3: 'every application links to the exact verified CV artefact that was sent'; the `ok`-only repository predicate is the cross-phase contract Phase 7's attach query consumes."
behavior_unverified_items:
  - truth: "A tailored RenderPlan compiles through the real pinned Tectonic engine and its extracted pypdf text passes the real Layer-2 checks."
    test: "In the container (`docker compose run --rm app pytest -m latex`, or generate + compile a scored listing), compile a tailored plan with the real engine and confirm a PDF plus a passing merged verification_json."
    expected: "A real PDF is produced and the merged VerificationResult passes (or reports only warn-tier checks)."
    why_human: >-
      Tectonic is absent from this dry host by design (D-69); the hermetic lane overrides the
      engine with a stub writing a canned PDF and monkeypatches `extract_pdf_text` to a
      committed fixture. Presence and wiring of the real path are verified by code reading
      (`app/pipeline/tailor.py`), but no test in this environment exercises the real
      engine/extraction behaviour on a tailored plan.
overrides: []
advisory: []
human_verification:
  - test: "Container latex lane: generate + compile a tailored plan with the real Tectonic engine; confirm the PDF and the persisted verification_json."
    expected: "A real PDF and a passing (or warn-only) VerificationResult."
    why_human: "Tectonic is absent from the dry host; the hermetic lane stubs both engine and extraction (D-69)."
  - test: "Open the tailoring review and the blocked state; read the fail-vs-warn distinction and whether a block feels like a reviewable outcome."
    expected: "A failing check is visually distinct from a warning; the block reads as a reviewable outcome with a clear recovery."
    why_human: "Visual legibility and perceived layout are not observable from HTML presence."
---

# Phase 6: Tailoring + Verification — Verification Report

**Phase Goal:** A tailored, verified CV PDF the user can preview and download — shipped with its verification gate, never before it.
**Verified:** 2026-09-25T10:23:05Z
**Status:** gaps_found
**Re-verification:** Yes — after round-2 gap closure (06-08, 06-09)

**MVP-mode note:** ROADMAP.md marks Phase 6 `mode: mvp`, but the ROADMAP goal text is not in
user-story form. The plan `06-01-PLAN.md` `<objective>` supplies a valid MVP user story, used here
for User Flow Coverage:
*"As a job seeker working a ranked queue, I want to turn one listing into a CV tailored to it —
expressed as a typed patch over my real CV facts, verified, compiled and downloadable — so that
I can apply with a CV shaped to that job without ever risking a claim I cannot stand behind."*

## User Flow Coverage

| Step | Expected | Evidence in codebase | Status |
| ---- | -------- | -------------------- | ------ |
| Open tailoring page for a listing | `rank_first` (unscored) / generate control (scored) / disabled label when off | `app/api/tailoring.py:298-337`; `tailoring.html`; `test_the_disabled_switch_is_honoured_across_the_tailoring_surfaces` | ✓ |
| Generate a tailored patch | Exactly one `complete_structured` call → typed `TailoringPatch`; no artifact, no PDF | `app/pipeline/tailor.py:217-256`; `app/api/tailoring.py:352-410`; `tests/api/test_tailoring_generate.py` green | ✓ |
| Review preview + change log before compile | HTML preview beside change log; drops struck with reason; guard fields | `_tailoring_review.html`, `app/api/tailoring.py`; `tests/api/test_tailoring_review.py` green | ✓ |
| Compile the tailored CV | Re-ground → Layer 1 → render → real engine → Layer 2 → persist one row | `app/pipeline/tailor.py` | ✓ (real engine behaviour behavior-unverified here) |
| Download the verified PDF | inline preview; `?download=1` attachment; non-`ok` unreachable | `app/api/tailoring.py:501-530`, `cv_artifact_repo.py` ok-only SQL (`:173-174`, `:191-192`); tests green | ✓ |
| Outcome clause: apply without risking an unsupported claim | Gate blocks fabrication; no free-text reaches PDF; valid CVs verify | canary `tests/verify/test_no_free_text_path.py`, ok-only access control — **but check 4 still false-fails a valid CV and still silently misses a fabricated digit** | ✗ FAILED |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Generate produces exactly one typed patch from exactly one structured call, one audit row, no artifact/`.tex`/PDF. | ✓ VERIFIED | `app/pipeline/tailor.py:217-256`; `tests/pipeline/test_tailor_stage.py`, `tests/api/test_tailoring_generate.py` green |
| 2 | Apply-tailoring is a typed patch (move/reweight/demote/drop/reorder-section) over enumerated IDs, all-or-nothing, no free-text on the PDF path, bullet text byte-immutable. | ✓ VERIFIED | `app/domain/cv.py`; `tests/domain/test_patch_ops.py`; canary `tests/verify/test_no_free_text_path.py` green |
| 3 | The user can preview the tailored CV and its change log (drops/demotions with reasons) before compiling. | ✓ VERIFIED | `_tailoring_review.html`; `tests/api/test_tailoring_review.py` green; layout legibility human-judged |
| 4 | The verification gate implements the ten advertised checks (eleven results) with the correct severities (`metric_containment` hard-fail; checks 8/9 warn-only). | ✓ VERIFIED | `app/verify/plan_checks.py`, `text_checks.py:48-57,82-98,116-151`; `tests/verify/test_text_checks.py` green |
| 5 | Digit-bearing entry locations (`Dublin 2`, an Eircode, `Remote (GMT+1)`) do not false-fail check 4. | ✓ VERIFIED | `app/verify/numbers.py:163-181` (location folds into `allowed`); `tests/verify/test_numbers.py::test_a_digit_bearing_location_is_not_a_surplus_candidate`; independent repro passes |
| 6 | **Check 4 does not false-fail a valid CV when an earlier bullet names a later entry's org AND title.** | ✗ FAILED | `app/verify/numbers.py:151-156`; independent repro returns `fail ['exp/globex-2019:5']`; `06-REVIEW.md` CR-01; `06-VALIDATION.md` ESC-06-A — see Gaps |
| 7 | **Check 4 does not silently skip an unanchorable region (no fabricated-digit false negative).** | ✗ FAILED | `app/verify/numbers.py:249-264`, `app/verify/text_checks.py:86-88`; independent repro: fabricated `99` passes; `06-REVIEW.md` WR-01; `06-VALIDATION.md` ESC-06-B — see Gaps |
| 8 | A CV that fails verification is blocked (not downloadable), and no code path auto-repairs it. | ✓ VERIFIED | `app/pipeline/tailor.py:289` ("deliberately no repair path"); `cv_artifact_repo.py` ok-only SQL; `tests/verify/test_block_no_repair.py`, `tests/api/test_cv_artifact_blocked.py` green |
| 9 | The verified CV PDF can be previewed inline and downloaded (`?download=1`); no path is built from request text. | ✓ VERIFIED | `app/api/tailoring.py:501-530`; `tests/api/test_cv_pdf_route.py` green |
| 10 | WR-02: the four bullet ops ground `bullet_id`/`before_id` against the bullet-id set and `ReorderSection.section_id` against the section-id set, so a non-family id raises `UnknownIdError` before `_build_plan` (no phantom `ChangeRecord`). | ✓ VERIFIED | `app/domain/cv.py`; `tests/domain/test_patch_ops.py` green |
| 11 | WR-01b: `POST /listings/{id}/cv/compile` honours `tailoring_enabled=False` with `409 tailoring_disabled` BEFORE `load_facts`, with zero rows/files/backend calls; `GET .../cv/pdf` deliberately ungated. | ✓ VERIFIED | `app/api/tailoring.py:435-436` (before `:450`), `:503-505`; `tests/api/test_tailoring_review.py` green |
| 12 | 06-09 WR-01: a raised `complete_structured` transport error writes exactly one `purpose="tailor"`, `status="error"` row (exception class only), releases the in-flight slot, and surfaces as a typed 502 `tailoring_failed` rather than a bare 500. | ✓ VERIFIED | `app/pipeline/tailor.py:241-256`, `app/api/tailoring.py:387-392`; `tests/pipeline/test_tailor_stage.py`, `tests/api/test_tailoring_generate.py` green |
| 13 | A tailored `RenderPlan` compiles through the real pinned Tectonic engine and its extracted pypdf text passes the real Layer-2 checks. | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Real path present and wired (`app/pipeline/tailor.py`); no test in this environment exercises the real engine/extraction (Tectonic absent by design D-69; hermetic lane stubs both) — see Human Verification |

**Score:** 9/12 truths verified (2 failed: check-4 false positive and false negative; 1 present, behavior-unverified: real engine/extraction)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/verify/{base,plan_checks,numbers,text_checks,grounding}.py` | Layer 1 + Layer 2 checks, tokeniser, advisory band | ⚠️ WIRED, DEFECTIVE | Present and wired via `__init__`; `numbers.py` region anchoring is incorrect for two CV shapes (truths 6/7) |
| `app/pipeline/tailor.py` | One call, frozen prompt, two-layer compile path, no repair, audit-on-raise | ✓ VERIFIED | `:241-256` records the class-only error row; `:289` no repair |
| `app/api/tailoring.py` | 4 routes, auth seam, no path from request text, compile off-switch, typed 502 | ✓ VERIFIED | `Depends(current_user)` on all 4; guard at `:435`; typed 502 at `:387-392`; PDF at `:501-530` |
| `app/domain/cv.py` patch engine | Five typed ops, all-or-nothing, per-op-family grounding | ✓ VERIFIED | `_validate_patch`; `_change_for` single builder |
| `app/db/repositories/cv_artifact_repo.py` | Writer + ok-only accessors | ✓ VERIFIED | `compile_status == "ok"` predicate in SQL on both accessors (`:173-174`, `:191-192`) |
| `tests/fixtures/verify/digit_location_extract.txt`, `digit_skill_extract.txt` | Digit-bearing committed extractions | ✓ VERIFIED | Committed; `with_digit_location` / `with_digit_skill` builders; `novel_metric_extract.txt` untouched |
| `app/web/templates/html/{tailoring,_tailoring_review,_cv_findings}.html` | Page, preview+change log, findings | ✓ VERIFIED | Substantive; no `|safe` |
| Migration | none | ✓ VERIFIED | Alembic head `0004` (no new revision) |
| `tests/verify/test_numbers.py` regression for the org+title bullet case | A test that fails on the residual CR-02 | ✗ MISSING | The authored test (`test_a_bullet_naming_a_later_employer_does_not_bleed_into_its_region`) names the employer WITHOUT the title, so it passes while the defect persists (`06-REVIEW.md:125-126`) |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| generate route | `tailor_listing` → `complete_structured` → review fragment | call, no artifact row | WIRED | `app/api/tailoring.py:352-410` |
| compile route | `compile_tailored` → `apply_patch` → `verify_plan` → render → `engine.compile` → `extract_pdf_text` → `verify_text` → `insert_artifact` | direct call | WIRED | `app/pipeline/tailor.py` |
| `compile_tailored_cv` | `settings.tailoring_enabled` guard → `_error_fragment(TAILOR_SKIP_DISABLED)` | early return before `load_facts` | WIRED | `app/api/tailoring.py:435-436` before `:450` |
| `_entry_lines` anchor | `region_token_report` region start | substring match org+title | ⚠️ PARTIAL | `app/verify/numbers.py:151-156` — matches bullets (truth 6) |
| `_entry_lines` `found=False` | `check_metric_containment` skip | `not report.found` | ⚠️ PARTIAL | `app/verify/text_checks.py:86-88` — silent false negative (truth 7) |
| `tailor_listing` except | `llm_call_repo.record_llm_call(status="error")` → typed 502 | direct call | WIRED | `app/pipeline/tailor.py:241-256`; `app/api/tailoring.py:387-392` |
| PDF route | repository ok-only selection | `latest_for_listing(ok_only=True)` | WIRED | `app/api/tailoring.py:514`; `cv_artifact_repo.py:173-174` |
| `_validate_patch` | `UnknownIdError` → generate/compile route's invalid-patch branch | raise before `_build_plan` | WIRED | `app/domain/cv.py`; routes catch `(UnknownIdError, InvalidPatchError)` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| tailoring page state | `tailoring_state`, `latest`, `findings`, `history` | `score_repo.read_score_for_listing`, `cv_artifact_repo.*` | Yes — real DB reads | ✓ FLOWING |
| review fragment | `plan`, `patch`, `dropped_bullets`, `gap_bands` | `apply_patch(facts, patch)` over the loaded fact store | Yes | ✓ FLOWING |
| check-4 region report | `RegionReport.candidates` / `.allowed` | `region_token_report(plan, extracted_text)` | Yes — real extraction text (fixture in hermetic lane) | ✓ FLOWING (predicate defective, truths 6/7) |
| PDF route | `record.pdf_path` | `latest_for_listing(ok_only=True)` SQL | Yes | ✓ FLOWING |
| persisted verification | `verification_json` | merged `verify_plan` + `verify_text` dumps | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full hermetic suite | `.venv/bin/python -m pytest -q` | `1238 passed, 14 deselected, 2 xfailed in 840.08s` | ✓ PASS |
| Build clean | `.venv/bin/python -m compileall -q app` | clean | ✓ PASS |
| Digit-bearing location verifies (CR-01 fix) | independent repro over `region_token_report` + `check_metric_containment` | `candidates=['2']`, `allowed=['01','2','2020','2021']`, `pass` | ✓ PASS |
| Org-only bullet mention does not bleed (CR-02 literal case) | independent repro | regions `[]` / `[]`, `pass` | ✓ PASS |
| **Earlier bullet names later entry's org+title** | independent repro (two entries) | `fail ['exp/globex-2019:5']` — false-fails a valid CV | ✗ FAIL (truth 6) |
| **Fabricated digit in an unanchorable region** | independent repro (empty title; wrapped header) | fabricated `99` → region `found=False`, `candidates=[]`, `pass` | ✗ FAIL (truth 7) |
| Novel-metric negative control | `pytest tests/verify/test_text_checks.py::test_a_novel_metric_token_fails_metric_containment` | fail `['exp/northwind-labs-2021:3.12']` | ✓ PASS |
| Real-engine latex lane | `.venv/bin/python -m pytest -m latex` | cannot run on host — Tectonic absent (D-69) | ? SKIP |

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes and no PLAN-declared probes exist for this phase. Step 7c: NOT APPLICABLE.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| TAIL-01 | 06-01, 06-07, 06-09 | Generate a CV tailored to a specific listing | ✓ SATISFIED | one call → one patch; generate route; off-switch guard on compile; typed 502 on raise |
| TAIL-02 | 06-01, 06-09 | Typed patch over enumerated IDs, no free-text on the PDF path | ✓ SATISFIED | schema + canary test + raised-error audit row |
| TAIL-03 | 06-01 | Never rewrites/invents claims; bullet text immutable | ✓ SATISFIED | carried-through `Bullet` objects; test |
| TAIL-04 | 06-02, 06-05, 06-08 | Verification gate checks the compiled PDF for unsupported content | ✗ BLOCKED | check 4 false-fails a valid CV (truth 6) AND silently misses a fabricated digit (truth 7); `nyquist_compliant: false` |
| TAIL-05 | 06-04 | Failed CV blocked; cannot be downloaded or attached | ✓ SATISFIED (download) / DEFERRED (attach → Phase 7) | ok-only SQL + route; attach is Phase 7 |
| TAIL-06 | 06-02, 06-03 | Verification never auto-repairs — it blocks | ✓ SATISFIED | no repair branch; tests |
| TAIL-07 | 06-03 | Review the tailored CV and change log before compiling | ✓ SATISFIED | review route/template; guard; tests |
| TAIL-08 | 06-03, 06-06 | Anything dropped is listed explicitly with a reason | ✓ SATISFIED | `dropped_bullets` struck + reason; phantom-change path closed |
| UI-05 | 06-04, 06-07 | Preview and download the tailored CV PDF | ✓ SATISFIED | inline + `?download=1`; tests |

All 9 phase requirement IDs appear in at least one plan's `requirements:` field. No ORPHANED requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `app/verify/numbers.py` | 151-156 | Naked-substring org+title region anchor | 🛑 Blocker | Hard-fails a valid CV (truth 6) — same class as CR-02 |
| `app/verify/numbers.py` | 249-264; `text_checks.py` 86-88 | `found=False` → empty candidates → silent skip | 🛑 Blocker | Fabricated digit in an unanchorable region passes (truth 7) |
| `tests/verify/test_numbers.py` | 274-314 | Regression test names org but not title, so it passes while the defect persists | ⚠️ Warning | Gives false confidence (06-REVIEW.md:125-126) |
| `app/pipeline/tailor.py` | 223-256 | `try` wraps prompt assembly, so a non-attempt can write an audit row (IN-07) | ℹ️ Info | Latent audit-row inflation of the rolling-24h cap |
| `app/api/tailoring.py` | 272-288 | Duplicated blocked-artifact rendering alongside `_cv_findings.html` (IN-04) | ℹ️ Info | Two escaping paths can drift |
| `app/verify/text_checks.py` | 201 | `model_fields` lookup instead of the exported `VERIFIER_VERSION` (IN-02) | ℹ️ Info | Brittle indirection |
| `app/web/templates/html/tailoring.html` | 64 | History "Download PDF" links all select the newest `ok` row (IN-05) | ℹ️ Info | Misleading in a retained-history surface |
| `app/api/tailoring.py` | 444-447 | `patch.listing_id` never checked against the URL listing (IN-06) | ℹ️ Info | Audit-trail inconsistency a forged POST can create |

No `TBD`/`FIXME`/`XXX` debt markers were found in the phase's modified files. **No blocking check was weakened** — `metric_containment` still returns `_fail`; `page_budget`/`layout_ats` remain the only `_warn` checks. **No new dependency added.** **Alembic head is still `0004`.**

### Human Verification Required

1. **Real-engine tailored compile** — In the container (`docker compose run --rm app pytest -m latex`, or generate + compile a scored listing), compile a tailored plan with the real pinned Tectonic engine; confirm a real PDF and the persisted merged `verification_json`. The hermetic lane stubs engine and extraction (D-69).
2. **Fail-vs-warn legibility and block-as-outcome** — Open the tailoring review and the blocked state; confirm a failing check is visually distinct from a warning and that the block reads as a reviewable outcome with a clear recovery.

### Gaps Summary

Round-2 gap closure (06-08, 06-09) closed four prior items with evidence: the digit-bearing-location false-fail (truth 5), the WR-02 phantom-change grounding (truth 10), the compile-route off-switch (truth 11), and the raised-transport audit/502 path (truth 12). The suite is green (`1238 passed`) and the build is clean.

But the check-4 region segmentation remains incorrect in two directions, and both are reproduced independently here against HEAD:

1. **False positive (BLOCKER, truth 6).** `_entry_lines` (`app/verify/numbers.py:151-156`) anchors a region on any line containing both `squash(org)` and `squash(title)`. A bullet in an earlier entry that names a later entry's org and a title word ("Liaised with the Globex Inc Manager on 5 projects", or the review's "Partnered with Acme's Senior Engineer team to cut 5 incidents") matches first, starts the later region one line early, and donates the earlier digit as a surplus candidate. `check_metric_containment` returns `fail` (`['exp/globex-2019:5']` in my repro), so a correct, ordinary CV is un-downloadable and the only recovery re-runs the same predicate. This is the residual of the CR-02 class round 2 claimed to close; `06-REVIEW.md` re-raises it as CR-01 (Critical) and `06-VALIDATION.md` as ESC-06-A.

2. **False negative (BLOCKER, truth 7).** When no single line carries both needles — an empty/all-punctuation `title`, or a long org+title that wraps — the region is reported `found=False`, `candidates=[]`, and check 4 skips it. A fabricated `99` inside the region passes silently. Corroborated by `06-REVIEW.md` WR-01 and `06-VALIDATION.md` ESC-06-B.

Neither is registered as a failing test: the suite is green precisely because the authored regression test uses an org-only bullet and the split-header case is pinned as an accepted trade-off. `06-VALIDATION.md` already records `nyquist_compliant: false` for these two escalated findings. Because a must-have truth is FAILED, the phase goal ("a tailored, verified CV PDF the user can preview and download") is not achieved for the affected CV shapes.

A fix is available and was checked by the reviewer: add a structural discriminator a bullet cannot satisfy — require the entry's date-range needle on the candidate line or its successor (the committed extraction places the date-range adjacent to the header, `tests/fixtures/verify/base_extract.txt`), or require the `---` header separator. Either preserves `base_extract.txt` found, the `novel_metric_extract.txt` negative control failing, and the last-region-runs-to-end-of-text property.

---

_Verified: 2026-09-25T10:23:05Z_
_Verifier: the agent (gsd-verifier)_
