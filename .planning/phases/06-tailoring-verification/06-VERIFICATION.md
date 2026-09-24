---
phase: 06-tailoring-verification
verified: 2026-09-24T23:23:38Z
status: human_needed
score: 9/10 must-haves verified
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
  - .planning/phases/06-tailoring-verification/06-CONTEXT.md
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
  - tests/api/test_tailoring_review.py
  - tests/domain/test_patch_ops.py
  - tests/fixtures/verify/digit_skill_extract.txt
  - tests/verify/fixtures.py
  - tests/verify/test_numbers.py
  - tests/verify/test_text_checks.py
covered_digest: "v1:sha256:5d9ffcdf1b22ead2cfbef823ead539641ca6a4b7933644bf283e0db3b9e2016f"
behavior_unverified: 1
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 5/6
  gaps_closed:
    - "The verification gate's metric containment (check 4) correctly identifies unsupported content, so a valid tailored CV is verifiable and downloadable (roadmap success criterion 3). (CR-01 — BLOCKER)"
    - "The date-like-number exclusion in metric containment is region-scoped (D-113). (WR-03)"
    - "The TailoringPatch op fields are grounded such that a change-log entry always describes a change that actually occurred (TAIL-08 honesty). (WR-02)"
  gaps_remaining: []
  regressions: []
behavior_unverified_items:
  - truth: "A tailored RenderPlan compiles through the real pinned Tectonic engine and its extracted pypdf text passes the real Layer-2 checks."
    test: "In the container (`docker compose run --rm app pytest -m latex`, or generate + compile a scored listing), compile a tailored plan with the real engine and confirm a PDF plus a passing merged verification_json."
    expected: "A real PDF is produced and the merged VerificationResult passes (or reports only warn-tier checks)."
    why_human: >-
      Tectonic is absent from this dry host by design (D-69); the hermetic lane overrides the
      engine with a stub writing a canned PDF and monkeypatches `extract_pdf_text` to a
      committed fixture. Presence and wiring of the real path are verified by code reading
      (`app/pipeline/tailor.py`), but no test in this environment exercises the real
      engine/extraction behaviour on a tailored plan. This is unchanged by the gap-closure round.
advisory: []
human_verification:
  - test: "Container latex lane: generate + compile a tailored plan with the real Tectonic engine; confirm the PDF and the persisted verification_json."
    expected: "A real PDF and a passing (or warn-only) VerificationResult."
    why_human: "Tectonic is absent from the dry host; the hermetic lane stubs both engine and extraction (coverage D7/D8)."
  - test: "Open the tailoring review and the blocked state; read the fail-vs-warn distinction and whether a block feels like a reviewable outcome."
    expected: "A failing check is visually distinct from a warning; the block reads as a reviewable outcome with a clear recovery."
    why_human: "Visual legibility and perceived layout are not observable from HTML presence (coverage D5/D6)."
---

# Phase 6: Tailoring + Verification — Verification Report

**Phase Goal:** A tailored, verified CV PDF the user can preview and download — shipped with its verification gate, never before it.
**Verified:** 2026-09-24T23:23:38Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (06-05, 06-06, 06-07)

**MVP-mode note:** ROADMAP.md marks Phase 6 `mode: mvp`, but the ROADMAP goal text is not in
user-story form. The plan `06-01-PLAN.md` `<objective>` supplies a valid MVP user story, used here
for User Flow Coverage:
*"As a job seeker working a ranked queue, I want to turn one listing into a CV tailored to it —
expressed as a typed patch over my real CV facts, verified, compiled and downloadable — so that
I can apply with a CV shaped to that job without ever risking a claim I cannot stand behind."*

## User Flow Coverage

| Step | Expected | Evidence in codebase | Status |
| ---- | -------- | -------------------- | ------ |
| Open tailoring page for a listing | `rank_first` (unscored) / generate control (scored) / disabled label when off | `app/api/tailoring.py:291-337`, `tailoring.html`; `test_the_disabled_switch_is_honoured_across_the_tailoring_surfaces` | ✓ |
| Generate a tailored patch | Exactly one `complete_structured` call → typed `TailoringPatch`; no artifact, no PDF | `app/pipeline/tailor.py`, `app/api/tailoring.py:340-403`; `tests/api/test_tailoring_generate.py` green | ✓ |
| Review preview + change log before compile | HTML preview beside change log; drops struck with reason; guard fields | `_tailoring_review.html`, `app/api/tailoring.py`; `tests/api/test_tailoring_review.py` green | ✓ |
| Compile the tailored CV | Re-ground → Layer 1 → render → real engine → Layer 2 → persist one row | `app/pipeline/tailor.py` | ✓ (real engine behaviour behavior-unverified here) |
| Download the verified PDF | inline preview; `?download=1` attachment; non-ok unreachable | `app/api/tailoring.py:477-513`, `cv_artifact_repo.py` ok-only SQL; tests green | ✓ |
| Outcome clause: apply without risking an unsupported claim | Gate blocks fabrication; no free-text reaches PDF; valid digit-bearing CVs no longer dead | canary `tests/verify/test_no_free_text_path.py`, ok-only access control, CR-01 fixed | ✓ |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Apply-tailoring is a typed patch (move / reweight / demote / drop / reorder-section) over enumerated IDs, all-or-nothing, with no free-text field on the path to the PDF and bullet text byte-immutable. | ✓ VERIFIED | `app/domain/cv.py:601-809`; `tests/domain/test_patch_ops.py`; canary `tests/verify/test_no_free_text_path.py` green |
| 2 | Generate produces exactly one patch from exactly one structured call, records one audit row, writes no artifact and no `.tex`/PDF. | ✓ VERIFIED | `app/pipeline/tailor.py`; `tests/pipeline/test_tailor_stage.py`, `tests/api/test_tailoring_generate.py` green |
| 3 | The user can preview the tailored CV and its change log (drops and demotions with reasons) before compiling. | ✓ VERIFIED | `_tailoring_review.html`; `tests/api/test_tailoring_review.py` green; layout legibility human-judged |
| 4 | The verification gate implements all ten advertised checks (as eleven results), including metric containment with region-local date-like exclusion; checks 8/9 warn-only; `metric_containment` is a HARD FAIL. | ✓ VERIFIED | `app/verify/plan_checks.py`, `text_checks.py`, `numbers.py`; `metric_containment`→`_fail` (`text_checks.py:93`), only `page_budget`/`layout_ats`→`_warn` (`text_checks.py:120,146`); negative control fails |
| 5 | A CV that fails verification is blocked (not downloadable), and no code path auto-repairs it. | ✓ VERIFIED | `app/pipeline/tailor.py` ("deliberately no repair path"); `cv_artifact_repo.py` ok-only SQL; `tests/verify/test_block_no_repair.py`, `tests/api/test_cv_artifact_blocked.py` green |
| 6 | The verified CV PDF can be previewed inline and downloaded (`?download=1`); no path is built from request text. | ✓ VERIFIED | `app/api/tailoring.py:477-513`; `tests/api/test_cv_pdf_route.py` (7 tests) green |
| 7 | **GAP 1 + WR-03 closed:** check 4's regions are region-local — an entry's OWN date cores, in-region page-number lines, and non-entry structured strings (section title / skill group / skill label / identity block) only where their string physically appears; a foreign date core is not excluded in another region; `VERIFIER_VERSION` is `1.0.1`; the `novel_metric_extract.txt` negative control still fails; `metric_containment` remains a hard fail. | ✓ VERIFIED | `app/verify/numbers.py:155-256`, `app/verify/base.py:22`; 4 new tests + independent repro (below) |
| 8 | **GAP 2 (WR-02) closed:** the four bullet ops resolve `bullet_id`/`before_id` against the bullet-id set and `ReorderSection.section_id` against the section-id set, so a non-family id raises `UnknownIdError` in `_validate_patch` before `_build_plan`; no phantom `ChangeRecord`; validation stays all-or-nothing (D-106). | ✓ VERIFIED | `app/domain/cv.py:601-655`; 3 new tests + independent repro (below) |
| 9 | **WR-01 closed:** `POST /listings/{id}/cv/compile` honours `settings.tailoring_enabled=False` with `409 data-error="tailoring_disabled"` BEFORE `load_facts`; zero rows/files/backend calls; the switch is live both directions; `GET /listings/{id}/cv/pdf` stays deliberately ungated. | ✓ VERIFIED | `app/api/tailoring.py:427-431` (guard), `:442` (load_facts, after), `:495` (pdf-route comment); 3 new tests green |
| 10 | A tailored `RenderPlan` compiles through the real pinned Tectonic engine and its extracted pypdf text passes the real Layer-2 checks. | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | Real path present and wired (`app/pipeline/tailor.py`); no test in this environment exercises the real engine/extraction (Tectonic absent by design D-69; hermetic lane stubs both) — see Human Verification |

**Score:** 9/10 truths verified (1 present, behavior-unverified: real engine/extraction)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/verify/{base,plan_checks,numbers,text_checks,grounding}.py` | Layer 1 + Layer 2 checks, tokeniser, advisory band | ✓ VERIFIED | Present, wired via `__init__`; `numbers.py` region-local construction at `:203-256` |
| `app/verify/numbers.py` `non_entry_structured_strings` / `_region_structured_cores` | Non-entry structured-string exclusion, region-local | ✓ VERIFIED | `:155-200`; exported in `__all__`; consumed by `region_token_report` |
| `app/pipeline/tailor.py` | One call, frozen prompt, two-layer compile path | ✓ VERIFIED | Real engine path present; hermetic tests stub engine/extraction |
| `app/api/tailoring.py` | 4 routes, auth seam, no path from request text, compile off-switch | ✓ VERIFIED | `Depends(current_user)` on all 4; guard at `:427` |
| `app/domain/cv.py` patch engine | Five typed ops, all-or-nothing, per-op-family grounding | ✓ VERIFIED | `_validate_patch:601-655`; `_change_for` single builder |
| `app/db/repositories/cv_artifact_repo.py` | Writer + ok-only accessors | ✓ VERIFIED | `compile_status == "ok"` predicate in SQL on both accessors (`:173-174`, `:191-192`) |
| `tests/fixtures/verify/digit_skill_extract.txt` | Digit-bearing Skills extraction | ✓ VERIFIED | Committed; `infrastructure AWS S3` row; `novel_metric_extract.txt` untouched |
| `app/web/templates/html/{tailoring,_tailoring_review,_cv_findings}.html` | Page, preview+change log, findings | ✓ VERIFIED | Substantive; no `|safe` |
| Migration | none | ✓ VERIFIED | Alembic head `0004` (`0001..0004`; no new revision) |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| generate route | `tailor_listing` → `complete_structured` → review fragment | call, no artifact row | WIRED | `app/api/tailoring.py:340-403` |
| compile route | `compile_tailored` → `apply_patch` → `verify_plan` → render → `engine.compile` → `extract_pdf_text` → `verify_text` → `insert_artifact` | direct call | WIRED | `app/pipeline/tailor.py` |
| `compile_tailored_cv` | `settings.tailoring_enabled` guard → `_error_fragment(TAILOR_SKIP_DISABLED)` | early return before `load_facts` | WIRED | `app/api/tailoring.py:427-431` (before `:442`) |
| `_validate_patch` | `UnknownIdError` → generate/compile route's invalid-patch branch | raise before `_build_plan` | WIRED | `app/domain/cv.py:618-624`; routes catch `(UnknownIdError, InvalidPatchError)` |
| `_region_structured_cores` | `non_entry_structured_strings` | plan strings scoped to region text | WIRED | `app/verify/numbers.py:182-200` |
| `VERIFIER_VERSION` | `VerificationResult.verifier_version` → persisted `verification_json` | default field | WIRED | `app/verify/base.py:22,50` |
| PDF route | repository ok-only selection | `latest_for_listing(ok_only=True)` | WIRED | `app/api/tailoring.py:491` |
| `main.py` | tailoring router | `include_router` | WIRED | `app/main.py` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| tailoring page state | `tailoring_state`, `latest`, `findings`, `history` | `score_repo.read_score_for_listing`, `cv_artifact_repo.*` | Yes — real DB reads | ✓ FLOWING |
| review fragment | `plan`, `patch`, `dropped_bullets`, `gap_bands` | `apply_patch(facts, patch)` over the loaded fact store | Yes | ✓ FLOWING |
| check-4 region report | `RegionReport.candidates` / `.allowed` | `region_token_report(plan, extracted_text)` | Yes — real extraction text (fixture in hermetic lane) | ✓ FLOWING |
| PDF route | `record.pdf_path` | `latest_for_listing(ok_only=True)` SQL | Yes | ✓ FLOWING |
| persisted verification | `verification_json` | merged `verify_plan` + `verify_text` dumps | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full hermetic suite | `.venv/bin/python -m pytest -q` | 1231 passed, 14 deselected, 2 xfailed (360s) | ✓ PASS |
| Build clean | `.venv/bin/python -m compileall -q app` | clean | ✓ PASS |
| 11 gap-closure tests | targeted `pytest` (4 numbers/text_checks + 3 patch_ops + 3 tailoring_review + negative control) | 11 passed | ✓ PASS |
| CR-01 repro (digit-bearing skill label) | `verify_text(...)` on `digit_skill_extract.txt` | `metric_containment: pass`, `offending: []`, `passed: True`; independent old-style simulation shows `3` (from `AWS S3`) WAS a surplus candidate under document-wide exclusion | ✓ PASS (fixed) |
| Region-local negative check | absent skill label must not excuse a digit | candidates `['3']` from the bullet, not the skill; region-local holds | ✓ PASS |
| Novel-metric negative control | `verify_text(...)` on `novel_metric_extract.txt` | `metric_containment: fail ['exp/northwind-labs-2021:3.12']`, `passed: False` | ✓ PASS (still fails) |
| WR-02 repro (skill/section id to bullet op) | `apply_patch(...)` | `UnknownIdError` for `skill.python` and section id; `skill.python`/`sec.skills` confirmed present in the full fact-id set (so old grounding accepted them) | ✓ PASS (fixed) |
| Real-engine latex lane | `.venv/bin/python -m pytest -m latex` | cannot run on host — Tectonic absent (D-69) | ? SKIP |

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes and no PLAN-declared probes exist for this phase. Step 7c: NOT APPLICABLE.

### Decision Coverage

All trackable CONTEXT.md decisions are honored by shipped artifacts: **17/17** (`check.decision-coverage-verify`, non-blocking).

### Test Quality Audit

| Test File | Linked Req | Active | Skipped | Circular | Assertion Level | Verdict |
|-----------|-----------|--------|---------|----------|-----------------|---------|
| `tests/verify/test_numbers.py` | TAIL-04 | 15+ | 0 | no | Value | ✓ |
| `tests/verify/test_text_checks.py` | TAIL-04 | 12+ | 0 | no | Value (status + `offending`) | ✓ |
| `tests/domain/test_patch_ops.py` | TAIL-08 | 15+ | 0 | no | Behavioral (raise + locus) | ✓ |
| `tests/api/test_tailoring_review.py` | TAIL-01/TAIL-07 | 20+ | 0 | no | Behavioral (409 + zero rows/files/calls) | ✓ |

**Disabled tests on requirements:** 0. **Circular patterns detected:** 0 (fixtures are committed extractions, not system-generated). **Insufficient assertions:** 0. Gap tests assert value/behavior level (specific `offending`, zero artifact rows, engine `calls == []`), not existence.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| TAIL-01 | 06-01, 06-07 | Generate a CV tailored to a specific listing | ✓ SATISFIED | one call → one patch; generate route; off-switch guard on compile |
| TAIL-02 | 06-01 | Typed patch over enumerated IDs, no free-text on the PDF path | ✓ SATISFIED | schema + canary test |
| TAIL-03 | 06-01 | Never rewrites/invents claims; bullet text immutable | ✓ SATISFIED | carried-through `Bullet` objects; test |
| TAIL-04 | 06-02, 06-05 | Verification gate checks the compiled PDF for unsupported content | ✓ SATISFIED | all ten checks present; check 4 now region-local; negative control fails |
| TAIL-05 | 06-04 | Failed CV blocked; cannot be downloaded or attached | ✓ SATISFIED (download) / DEFERRED (attach → Phase 7) | ok-only SQL + route; attach is Phase 7 |
| TAIL-06 | 06-02 | Verification never auto-repairs — it blocks | ✓ SATISFIED | no repair branch; tests |
| TAIL-07 | 06-03 | Review the tailored CV and change log before compiling | ✓ SATISFIED | review route/template; guard; tests |
| TAIL-08 | 06-03, 06-06 | Anything dropped is listed explicitly with a reason | ✓ SATISFIED | `dropped_bullets` struck + reason; phantom-change path now closed |
| UI-05 | 06-04 | Preview and download the tailored CV PDF | ✓ SATISFIED | inline + `?download=1`; tests |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `app/api/tailoring.py` | 272-288 | Duplicated blocked-artifact rendering alongside `_cv_findings.html` | ℹ️ Info | Two escaping paths can drift (IN-05); unchanged, not a gap |
| `app/domain/cv.py` | 775-776 | `# pragma: no cover` unreachable "section lost all entries" guard | ℹ️ Info | D-106 invariant not actually exercised (IN-01); unchanged |
| `app/verify/text_checks.py` | `verifier_version` | `model_fields` lookup instead of the exported constant | ℹ️ Info | Brittle lookup (IN-03); unchanged |

No `TBD`/`FIXME`/`XXX` debt markers were found in the phase's modified files (verified by grep over `app/verify`, `app/domain/cv.py`, `app/api/tailoring.py`, and the linked test modules).

**No blocking check was weakened or deleted.** Diff `ac6aa74..HEAD` touches `app/verify/*` only in `numbers.py` (region/allowed construction + docstring) and `base.py` (`VERIFIER_VERSION` `1.0.0`→`1.0.1`). `metric_containment` still returns `_fail`; `page_budget`/`layout_ats` remain the only `_warn` checks. **No new dependency added** (no diff to `pyproject.toml`/`requirements.txt` during Phase 6). **Alembic head is still `0004`.**

### Advisory (New Scope, Unevidenced)

| # | Finding | Category | Why Advisory |
|---|---------|----------|--------------|
| — | None | — | No new-scope findings were raised this round. |

### Human Verification Required

1. **Real-engine tailored compile** — In the container (`docker compose run --rm app pytest -m latex`, or generate + compile a scored listing), compile a tailored plan with the real pinned Tectonic engine; confirm a real PDF and the persisted merged `verification_json`. The hermetic lane stubs engine and extraction (D-69).
2. **Fail-vs-warn legibility and block-as-outcome** — Open the tailoring review and the blocked state; confirm a failing check is visually distinct from a warning and that the block reads as a reviewable outcome with a clear recovery (visual judgment; coverage D5/D6).

### Gaps Summary

All three prior gaps are closed with evidence, not assertion:

- **CR-01 (BLOCKER) / WR-03 — closed.** `app/verify/numbers.py` now builds each region's excluded/allowed set locally: that entry's OWN date cores, page-number lines inside the region, and the digit cores of non-entry structured strings only where the string physically appears in the region (`_region_structured_cores`, `:182-200`; loop `:236-255`). The two document-wide pre-loops (the union of every entry's dates and the document-wide page-number scan) are deleted. `VERIFIER_VERSION` is `1.0.1`. Independently reproduced: the `AWS S3` `3` that the old document-wide code made a surplus candidate is now grounded and `metric_containment` passes; the `novel_metric_extract.txt` `Python 3.12` control still fails with `exp/northwind-labs-2021:3.12`; a skill label absent from a region does not excuse a digit. `metric_containment` remains a hard fail.
- **WR-02 — closed.** `_validate_patch` (`app/domain/cv.py:601-655`) selects the grounding set per op family: the four bullet ops against `bullet_ids`, `ReorderSection` against `section_ids`, gap/suggestion references against the full fact-id set. Independently reproduced: `skill.python` and `sec.skills` are present in the full fact-id set (so the old code accepted them) and now both raise `UnknownIdError` before `_build_plan`, so no phantom `ChangeRecord`; `_change_for` still appears exactly once. Validation is still all-or-nothing.
- **WR-01 — closed.** `compile_tailored_cv` (`app/api/tailoring.py:427-431`) refuses with `409 data-error="tailoring_disabled"` before `load_facts` (`:442`); the guard is byte-for-byte the generate route's. Tests prove zero `cv_artifacts` rows, zero files under the artifacts dir, zero engine calls, zero backend calls, and that re-enabling the switch compiles the same round-tripped fields to exactly one `ok` row. `GET .../cv/pdf` stays deliberately ungated (`:495` comment).

The only remaining item is the behavior-unverified real-engine path (truth 10), which this dry host cannot exercise by design; it routes to the human container check. The Phase 7 "attach" half of TAIL-05 remains correctly deferred per ROADMAP Phase 7 success criterion 3.

---

_Verified: 2026-09-24T23:23:38Z_
_Verifier: the agent (gsd-verifier)_
